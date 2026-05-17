"""Nightly upload scheduling.

APScheduler runs a single cron job at config.upload_hour:upload_minute.
Each fire calls UploadEngine.run_batch(). If the engine is already
running (concurrent fires can't happen here — APScheduler serializes
the same job — but a manual trigger can race), the second invocation
just no-ops.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import Config

log = logging.getLogger(__name__)


class NightlyScheduler:
    def __init__(self, config: Config, runner: Callable[[], None]):
        self._config = config
        self._runner = runner
        self._sched = BackgroundScheduler(daemon=True)
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        self._install_job()
        self._sched.start()
        log.info("scheduler started: cron %02d:%02d",
                 self._config.upload_hour, self._config.upload_minute)

    def stop(self) -> None:
        try:
            self._sched.shutdown(wait=False)
        except Exception:
            pass

    def reschedule(self, hour: int, minute: int) -> None:
        self._config.upload_hour = hour
        self._config.upload_minute = minute
        self._install_job()

    def trigger_now(self) -> None:
        """Manual one-off run."""
        threading.Thread(target=self._guarded_run, daemon=True,
                          name="manual-upload").start()

    def _install_job(self) -> None:
        trigger = CronTrigger(
            hour=self._config.upload_hour,
            minute=self._config.upload_minute,
        )
        self._sched.add_job(
            self._guarded_run,
            trigger=trigger,
            id="nightly-upload",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,  # if the laptop was asleep at 2am, run within the hour
        )

    def _guarded_run(self) -> None:
        with self._lock:
            if self._running:
                log.info("upload already running; skipping")
                return
            self._running = True
        try:
            self._runner()
        except Exception:
            log.exception("upload run crashed")
        finally:
            with self._lock:
                self._running = False
