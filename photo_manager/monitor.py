"""Filesystem monitoring: watch the source folder, copy new media into
the library's Inbox, record an inbox row."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .database import Database
from .exif import extract, is_supported
from .folders import LibraryLayout, move_file
from .models import Photo, PhotoStatus

log = logging.getLogger(__name__)


class SourceFolderMonitor:
    """Watches `source_folder` and ingests new files into Inbox.

    Uses watchdog if available (event-driven, no polling). Falls back to
    a 5-second poll loop if watchdog isn't installed — same semantics,
    just less efficient.
    """

    def __init__(
        self,
        source_folder: Path,
        db: Database,
        layout: LibraryLayout,
        on_added: Optional[Callable[[Photo], None]] = None,
    ):
        self.source_folder = Path(source_folder)
        self.db = db
        self.layout = layout
        self.on_added = on_added
        self._stop = threading.Event()
        self._observer = None
        self._poller: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.source_folder.exists():
            log.warning("source folder %s does not exist yet", self.source_folder)
            self.source_folder.mkdir(parents=True, exist_ok=True)
        self.scan_once()  # catch up on what's already there
        self._start_watcher()

    def stop(self) -> None:
        self._stop.set()
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        if self._poller:
            self._poller.join(timeout=5)

    def scan_once(self) -> int:
        """One-shot scan; safe to call any time."""
        count = 0
        for path in sorted(self.source_folder.iterdir()):
            if path.is_file() and is_supported(path):
                if self._ingest(path):
                    count += 1
        return count

    def _start_watcher(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:
            log.info("watchdog not installed; falling back to polling")
            self._poller = threading.Thread(
                target=self._poll_loop, daemon=True, name="source-poll",
            )
            self._poller.start()
            return

        handler = _Handler(self._ingest)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.source_folder), recursive=False)
        self._observer.start()

    def _poll_loop(self) -> None:
        while not self._stop.wait(5):
            try:
                self.scan_once()
            except Exception:
                log.exception("scan failed")

    def _ingest(self, path: Path) -> bool:
        """Move a single source file into Inbox, dedup'd by hash."""
        if not path.exists() or not is_supported(path):
            return False
        if not _is_stable(path):
            return False  # still being written

        try:
            info = extract(path)
        except Exception:
            log.exception("EXIF/hash failed for %s", path)
            return False

        existing = self.db.get_photo_by_hash(info.file_hash)
        if existing:
            log.info("dedup: %s matches existing photo id=%s", path.name, existing.id)
            try:
                path.unlink()  # remove the duplicate source
            except OSError:
                pass
            return False

        try:
            moved = move_file(path, self.layout.dir_for(PhotoStatus.INBOX))
        except Exception:
            log.exception("could not move %s into Inbox", path)
            return False

        photo = Photo(
            id=None,
            filename=moved.name,
            filepath=str(moved),
            status=PhotoStatus.INBOX,
            date_added=datetime.utcnow(),
            file_hash=info.file_hash,
            file_size=info.file_size,
            width=info.width,
            height=info.height,
            date_taken=info.date_taken,
            camera_model=info.camera_model,
            exif_json=info.exif_json,
        )
        try:
            photo.id = self.db.insert_photo(photo)
        except Exception:
            log.exception("DB insert failed for %s", moved)
            return False

        log.info("ingested %s (id=%s)", moved.name, photo.id)
        if self.on_added:
            try:
                self.on_added(photo)
            except Exception:
                log.exception("on_added callback failed")
        return True


def _is_stable(path: Path, *, settle_sec: float = 1.0) -> bool:
    """Cheap heuristic: file size stops changing for `settle_sec`."""
    try:
        s1 = path.stat().st_size
    except OSError:
        return False
    time.sleep(settle_sec)
    try:
        s2 = path.stat().st_size
    except OSError:
        return False
    return s1 == s2 and s1 > 0


try:
    from watchdog.events import FileSystemEventHandler

    class _Handler(FileSystemEventHandler):  # type: ignore[misc]
        def __init__(self, ingest):
            self._ingest = ingest

        def on_created(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            self._ingest(Path(event.src_path))

        def on_moved(self, event):  # type: ignore[override]
            if event.is_directory:
                return
            self._ingest(Path(event.dest_path))
except ImportError:  # pragma: no cover
    pass
