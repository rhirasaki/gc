"""Upload engine.

A single nightly invocation does roughly this:

    1. Read all photos with status=PENDING that are due (per backoff schedule).
    2. Move them PENDING -> UPLOADING (DB + folder) one by one.
    3. Pool a bounded number of workers, each running upload_one() with a
       per-file timeout. On success: UPLOADING -> UPLOADED + persist
       google_photos_id. On failure: classify the error; move back to
       PENDING (transient) or to FAILED (permanent / out of retries).
    4. If the batch hits too many timeouts, shrink the pool and re-run
       the remaining photos individually.

Two invariants you can rely on:
  - We never delete the source file. Files only *move*.
  - A photo's row reflects truth: if the row says UPLOADED with a
    google_photos_id, that media item exists in Google Photos (checked
    by recovery on next start if we crashed mid-flight).
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import Config
from .database import Database
from .folders import LibraryLayout, move_file
from .google_photos import GooglePhotosClient, PhotosAPIError
from .models import ErrorKind, PhotoStatus
from .retry import classify_exception, classify_http, next_delay, should_retry

log = logging.getLogger(__name__)


@dataclass
class UploadOutcome:
    photo_id: int
    success: bool
    google_photos_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    kind: Optional[ErrorKind] = None


class UploadEngine:
    def __init__(
        self,
        db: Database,
        layout: LibraryLayout,
        client: GooglePhotosClient,
        config: Config,
    ):
        self.db = db
        self.layout = layout
        self.client = client
        self.config = config
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    # -- entry point ---------------------------------------------------

    def run_batch(self, *, album_id: Optional[str] = None) -> dict:
        """Process due PENDING photos. Returns a summary dict."""
        self._cancel.clear()
        due = self._due_pending()
        if not due:
            log.info("upload run: no due pending photos")
            return {"considered": 0, "success": 0, "failed": 0, "deferred": 0}

        batch_id = self.db.start_batch(len(due))
        log.info("upload run: batch=%s photos=%d", batch_id, len(due))

        batch_size = max(self.config.min_batch_size,
                         min(self.config.batch_size, self.config.max_batch_size))
        success = failed = 0
        remaining = list(due)
        timeouts_in_pool = 0

        while remaining and not self._cancel.is_set():
            chunk, remaining = remaining[:batch_size], remaining[batch_size:]
            outcomes = self._process_chunk(chunk, batch_id, album_id)
            pool_timeouts = sum(
                1 for o in outcomes if o.error_code in {"TIMEOUT", "BATCH_TIMEOUT"}
            )
            for o in outcomes:
                if o.success:
                    success += 1
                else:
                    failed += 1
            if pool_timeouts >= max(1, len(chunk) // 2) and batch_size > self.config.min_batch_size:
                batch_size = max(self.config.min_batch_size, batch_size // 2)
                log.warning("shrinking batch size to %d after %d timeouts",
                            batch_size, pool_timeouts)
                timeouts_in_pool += pool_timeouts

        self.db.finish_batch(batch_id, success=success, failure=failed)
        log.info("upload run: done success=%d failed=%d", success, failed)
        return {
            "considered": len(due),
            "success": success,
            "failed": failed,
            "deferred": 0,
        }

    # -- selection -----------------------------------------------------

    def _due_pending(self) -> list:
        """PENDING photos whose backoff window has elapsed."""
        now = datetime.utcnow()
        due = []
        for p in self.db.photos_by_status(PhotoStatus.PENDING):
            if p.attempt_count == 0 or p.last_attempt_timestamp is None:
                due.append(p)
                continue
            wait_sec = next_delay(p.attempt_count)
            if p.last_attempt_timestamp + timedelta(seconds=wait_sec) <= now:
                due.append(p)
            else:
                log.debug("photo %s deferred (attempt=%d, wait=%ds)",
                          p.id, p.attempt_count, wait_sec)
        return due

    # -- per-chunk -----------------------------------------------------

    def _process_chunk(self, chunk, batch_id: int, album_id: Optional[str]):
        outcomes: list[UploadOutcome] = []
        # Move all to UPLOADING up-front so the DB shows accurate state if we crash.
        prepared: list = []
        for p in chunk:
            try:
                p = self._mark_uploading(p)
                prepared.append(p)
            except Exception as e:
                log.exception("could not prepare %s", p.filepath)
                outcomes.append(UploadOutcome(
                    photo_id=p.id, success=False,
                    error_code="PREP_FAILED", error_message=str(e),
                ))

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, len(prepared)),
            thread_name_prefix="upload",
        ) as ex:
            futures = {ex.submit(self._upload_one, p, album_id): p for p in prepared}
            for fut in concurrent.futures.as_completed(futures):
                p = futures[fut]
                try:
                    outcome = fut.result()
                except Exception as e:  # pragma: no cover — defensive
                    log.exception("worker crashed on %s", p.filepath)
                    outcome = UploadOutcome(
                        photo_id=p.id, success=False,
                        error_code="WORKER_CRASH", error_message=str(e),
                        kind=ErrorKind.UNKNOWN,
                    )
                self._finalize(outcome, p, batch_id)
                outcomes.append(outcome)
        return outcomes

    # -- single upload -------------------------------------------------

    def _upload_one(self, photo, album_id: Optional[str]) -> UploadOutcome:
        try:
            result = self.client.upload_one(
                Path(photo.filepath),
                album_id=album_id,
                timeout=self.config.per_file_timeout_sec,
            )
            return UploadOutcome(
                photo_id=photo.id, success=True,
                google_photos_id=result.google_photos_id,
            )
        except PhotosAPIError as e:
            cls = classify_http(e.status_code, e.message)
            return UploadOutcome(
                photo_id=photo.id, success=False,
                error_code=cls.code, error_message=cls.message, kind=cls.kind,
            )
        except Exception as e:
            cls = classify_exception(e)
            return UploadOutcome(
                photo_id=photo.id, success=False,
                error_code=cls.code, error_message=cls.message, kind=cls.kind,
            )

    # -- state transitions --------------------------------------------

    def _mark_uploading(self, photo):
        src = Path(photo.filepath)
        if not src.exists():
            # File vanished between scheduling and upload — treat as permanent failure.
            raise FileNotFoundError(photo.filepath)
        dst = self.layout.dir_for(PhotoStatus.UPLOADING)
        moved = move_file(src, dst)
        return self.db.transition(
            photo.id, PhotoStatus.UPLOADING, new_filepath=str(moved),
        )

    def _finalize(self, outcome: UploadOutcome, photo, batch_id: int) -> None:
        if outcome.success:
            target_dir = self.layout.dir_for(PhotoStatus.UPLOADED, when=datetime.utcnow().date())
            moved = move_file(Path(photo.filepath), target_dir)
            self.db.transition(
                photo.id, PhotoStatus.UPLOADED,
                new_filepath=str(moved),
                google_photos_id=outcome.google_photos_id,
                mark_uploaded=True,
                reset_attempts=True,
            )
            self.db.record_attempt(photo.id, batch_id, "success")
            return

        # Failure path. Decide where the photo goes based on error class.
        from .retry import ClassifiedError
        cls = ClassifiedError(
            kind=outcome.kind or ErrorKind.UNKNOWN,
            code=outcome.error_code or "UNKNOWN",
            message=outcome.error_message or "",
        )
        next_attempt = photo.attempt_count + 1
        if not should_retry(cls, next_attempt, self.config.max_retries):
            # Move to /Failed with a sidecar error log.
            target_dir = self.layout.dir_for(PhotoStatus.FAILED)
            moved = move_file(Path(photo.filepath), target_dir)
            _write_error_log(moved, cls.code, cls.message, next_attempt)
            self.db.transition(
                photo.id, PhotoStatus.FAILED,
                new_filepath=str(moved),
                error_code=cls.code,
                error_message=cls.message,
                bump_attempt=True,
            )
            self.db.record_attempt(photo.id, batch_id, "failed",
                                    error_code=cls.code, error_message=cls.message)
            log.warning("permanent failure %s: %s", photo.filepath, cls.message)
            return

        # Transient: back to /Pending for the next cycle.
        target_dir = self.layout.dir_for(PhotoStatus.PENDING)
        moved = move_file(Path(photo.filepath), target_dir)
        self.db.transition(
            photo.id, PhotoStatus.PENDING,
            new_filepath=str(moved),
            error_code=cls.code,
            error_message=cls.message,
            bump_attempt=True,
        )
        self.db.record_attempt(photo.id, batch_id, "retry",
                                error_code=cls.code, error_message=cls.message)
        log.info("transient failure %s (attempt %d/%d): %s",
                 photo.filepath, next_attempt, self.config.max_retries, cls.message)


def _write_error_log(photo_path: Path, code: str, message: str, attempt: int) -> None:
    sidecar = photo_path.with_name(photo_path.stem + "_error.txt")
    try:
        sidecar.write_text(
            f"Timestamp: {datetime.utcnow().isoformat()}Z\n"
            f"Photo:     {photo_path.name}\n"
            f"Code:      {code}\n"
            f"Attempts:  {attempt}\n"
            f"Message:   {message}\n"
        )
    except OSError:
        log.exception("could not write sidecar log for %s", photo_path)
