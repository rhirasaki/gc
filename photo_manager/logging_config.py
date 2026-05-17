"""Application logging with weekly rotation."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .config import log_dir


def setup_logging(level: int = logging.INFO) -> None:
    log_path = log_dir()
    log_path.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Drop any pre-existing handlers so re-init is idempotent.
    for h in list(root.handlers):
        root.removeHandler(h)

    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_path / "photo_manager.log",
        when="W0",       # Monday
        backupCount=4,   # keep last 4 weeks
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    root.addHandler(stream)
