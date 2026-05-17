"""Application controller: wires together all the moving parts.

The UI talks to the controller; the controller owns lifecycles for the
DB, scheduler, monitor, network probe, and uploader. Designed to be
constructable without a UI (so the CLI / tests can drive it directly).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from .config import Config, db_path
from .database import Database
from .folders import LibraryLayout
from .google_photos import GooglePhotosClient
from .monitor import SourceFolderMonitor
from .network import NetworkMonitor
from .recovery import recover_on_startup, sweep_stalled
from .scheduler import NightlyScheduler
from .uploader import UploadEngine

log = logging.getLogger(__name__)


class AppController:
    def __init__(self, config: Config):
        self.config = config
        self.db = Database(db_path())
        self.layout = LibraryLayout(Path(config.library_root)) if config.library_root else None
        self._client: Optional[GooglePhotosClient] = None
        self._engine: Optional[UploadEngine] = None
        self._monitor: Optional[SourceFolderMonitor] = None
        self._network: Optional[NetworkMonitor] = None
        self._scheduler: Optional[NightlyScheduler] = None

    # -- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if not self.config.library_root:
            log.info("library not configured; controller idle until setup completes")
            return
        if self.layout is None:
            self.layout = LibraryLayout(Path(self.config.library_root))
        self.layout.ensure()
        self.layout.cleanup_temp()

        # Recovery before anything else touches state.
        try:
            summary = recover_on_startup(self.db, self.layout, self._client, self.config)
            log.info("recovery summary: %s", summary)
        except Exception:
            log.exception("recovery failed")
        try:
            sweep_stalled(self.db, self.layout, self.config)
        except Exception:
            log.exception("stalled sweep failed")

        if self.config.source_folder:
            self._monitor = SourceFolderMonitor(
                Path(self.config.source_folder), self.db, self.layout,
            )
            self._monitor.start()

        self._network = NetworkMonitor(
            interval_sec=self.config.network_check_interval_sec,
            on_change=self._on_network_change,
        )
        self._network.start()

        self._scheduler = NightlyScheduler(self.config, self._run_upload)
        self._scheduler.start()

    def stop(self) -> None:
        for component in (self._monitor, self._network, self._scheduler):
            if component is not None:
                try:
                    component.stop()
                except Exception:
                    log.exception("stop failed for %s", component)
        try:
            self.db.close()
        except Exception:
            pass

    # -- auth ----------------------------------------------------------

    def authenticate(self) -> str:
        """Run OAuth flow. Returns the authenticated email (or '')."""
        from .auth import load_credentials
        creds = load_credentials(Path(self.config.oauth_client_secret_path))
        self._client = GooglePhotosClient(creds)
        if self.layout is not None:
            self._engine = UploadEngine(self.db, self.layout, self._client, self.config)
        return self._client.get_user_email() or ""

    def has_client(self) -> bool:
        return self._client is not None

    # -- actions -------------------------------------------------------

    def flag_for_upload(self, photo_id: int) -> None:
        from .models import PhotoStatus
        from .folders import move_file
        photo = self.db.get_photo(photo_id)
        if not photo:
            raise KeyError(photo_id)
        if photo.status != PhotoStatus.INBOX:
            return  # idempotent
        moved = move_file(Path(photo.filepath), self.layout.dir_for(PhotoStatus.PENDING))
        self.db.transition(photo_id, PhotoStatus.PENDING, new_filepath=str(moved))

    def retry_all_failed(self) -> int:
        from .models import PhotoStatus
        from .folders import move_file
        count = 0
        for photo in self.db.photos_by_status(PhotoStatus.FAILED):
            try:
                if Path(photo.filepath).exists():
                    moved = move_file(Path(photo.filepath),
                                       self.layout.dir_for(PhotoStatus.PENDING))
                    self.db.transition(photo.id, PhotoStatus.PENDING,
                                        new_filepath=str(moved),
                                        reset_attempts=True)
                else:
                    self.db.transition(photo.id, PhotoStatus.PENDING,
                                        reset_attempts=True)
                count += 1
            except Exception:
                log.exception("retry failed for %s", photo.filepath)
        return count

    def upload_now(self) -> dict:
        if self._engine is None:
            raise RuntimeError("not authenticated yet")
        return self._engine.run_batch()

    def status_counts(self) -> dict:
        return {k.value: v for k, v in self.db.status_counts().items()}

    # -- hooks ---------------------------------------------------------

    def _run_upload(self) -> None:
        if self._engine is None:
            log.info("scheduled run skipped: no engine (not authenticated)")
            return
        if self._network and not self._network.online:
            log.info("scheduled run skipped: offline")
            return
        self._engine.run_batch()

    def _on_network_change(self, online: bool) -> None:
        self.db.log_network(online)
        if online and self._engine is not None:
            # Connectivity returned — try to flush queued photos now.
            log.info("network back online; triggering catch-up upload")
            if self._scheduler:
                self._scheduler.trigger_now()
