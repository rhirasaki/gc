"""User-facing configuration.

App settings persist in two places:
  - On-disk JSON (paths, timeouts, batch size, schedule) — easy to edit.
  - OS keychain (OAuth tokens) — via `auth.py`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from platformdirs import user_config_dir, user_data_dir, user_log_dir


APP_NAME = "PhotoManager"


@dataclass
class Config:
    # Paths
    source_folder: str = ""           # where new photos land (watched)
    library_root: str = ""            # where Inbox/Pending/... live

    # Scheduling
    upload_hour: int = 2              # 24h clock
    upload_minute: int = 0

    # Upload behaviour
    batch_size: int = 5               # parallel uploads per batch
    min_batch_size: int = 1
    max_batch_size: int = 10
    per_file_timeout_sec: int = 300   # 5 minutes
    batch_timeout_sec: int = 1800     # 30 minutes
    max_retries: int = 5
    network_check_interval_sec: int = 30
    stalled_upload_grace_sec: int = 7200  # 2h — see scheduler cleanup

    # Cleanup
    delete_originals_after_days: Optional[int] = None  # None = keep

    # OAuth client (paths to user-provided credentials)
    oauth_client_secret_path: str = ""

    # Misc
    autostart: bool = False
    theme: str = "system"             # system | light | dark

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        path = path or config_path()
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return cls()
        # Drop unknown keys so old configs forward-load cleanly.
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Optional[Path] = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2))
        tmp.replace(path)


def config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False))


def data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, appauthor=False))


def log_dir() -> Path:
    return Path(user_log_dir(APP_NAME, appauthor=False))


def config_path() -> Path:
    return config_dir() / "config.json"


def db_path() -> Path:
    return data_dir() / "photos.sqlite"
