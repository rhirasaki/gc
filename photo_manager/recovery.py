"""Crash recovery.

Invariant we restore on every startup: no photo remains in UPLOADING.
If a crash left the row there, we either:
  - confirm it landed in Google Photos (verify by google_photos_id, if we
    stored one) and finish the transition to UPLOADED; or
  - move the file back to /Pending and increment the retry counter.

Also picks up any stalled UPLOADING files (older than the grace window)
even when the API can't tell us — better to retry than to leave them.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import Config
from .database import Database
from .folders import LibraryLayout, move_file
from .google_photos import GooglePhotosClient
from .models import PhotoStatus

log = logging.getLogger(__name__)


def recover_on_startup(
    db: Database,
    layout: LibraryLayout,
    client: Optional[GooglePhotosClient],
    config: Config,
) -> dict:
    """Reconcile UPLOADING rows. Returns a summary for logging/UI."""
    in_flight = db.photos_by_status(PhotoStatus.UPLOADING)
    log.info("recovery: %d photo(s) in UPLOADING", len(in_flight))
    confirmed = requeued = lost = 0

    for photo in in_flight:
        # Case 1: we got far enough to record a google_photos_id and can verify.
        if photo.google_photos_id and client is not None:
            try:
                if client.media_item_exists(photo.google_photos_id):
                    _confirm(db, layout, photo)
                    confirmed += 1
                    continue
            except Exception:
                log.exception("verify failed for %s", photo.filepath)

        # Case 2: no proof of success. Requeue.
        src = Path(photo.filepath)
        if not src.exists():
            # File is gone and we can't verify — mark FAILED so the user sees it.
            db.transition(
                photo.id, PhotoStatus.FAILED,
                error_code="MISSING_FILE",
                error_message="File missing during recovery",
                bump_attempt=True,
            )
            lost += 1
            continue

        dst = layout.dir_for(PhotoStatus.PENDING)
        try:
            moved = move_file(src, dst)
        except Exception:
            log.exception("could not move %s back to Pending", src)
            continue
        db.transition(
            photo.id, PhotoStatus.PENDING,
            new_filepath=str(moved),
            error_code="INTERRUPTED",
            error_message="Recovered from interrupted upload",
            bump_attempt=True,
        )
        requeued += 1

    return {"confirmed": confirmed, "requeued": requeued, "lost": lost}


def sweep_stalled(db: Database, layout: LibraryLayout, config: Config) -> int:
    """Move UPLOADING photos older than the grace window back to PENDING.

    Belt-and-braces for the case where the engine itself wedged — e.g. a
    misbehaving worker that never threw.
    """
    cutoff = datetime.utcnow() - timedelta(seconds=config.stalled_upload_grace_sec)
    swept = 0
    for photo in db.photos_by_status(PhotoStatus.UPLOADING):
        if photo.last_attempt_timestamp and photo.last_attempt_timestamp > cutoff:
            continue
        src = Path(photo.filepath)
        if not src.exists():
            continue
        try:
            moved = move_file(src, layout.dir_for(PhotoStatus.PENDING))
        except Exception:
            log.exception("sweep: could not move %s", src)
            continue
        db.transition(
            photo.id, PhotoStatus.PENDING,
            new_filepath=str(moved),
            error_code="STALLED",
            error_message="Stalled upload reset by sweeper",
            bump_attempt=True,
        )
        swept += 1
    if swept:
        log.warning("sweep: reset %d stalled uploads", swept)
    return swept


def _confirm(db: Database, layout: LibraryLayout, photo) -> None:
    """Finish a successful-but-uncommitted upload."""
    target_dir = layout.dir_for(PhotoStatus.UPLOADED, when=datetime.utcnow().date())
    src = Path(photo.filepath)
    if src.exists():
        moved = move_file(src, target_dir)
        new_path: Optional[str] = str(moved)
    else:
        new_path = None
    db.transition(
        photo.id, PhotoStatus.UPLOADED,
        new_filepath=new_path,
        mark_uploaded=True,
        reset_attempts=True,
    )
    log.info("recovery: confirmed %s already in Google Photos", photo.filename)
