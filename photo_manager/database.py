"""SQLite-backed state store.

Single source of truth for photo state. Every state transition is wrapped
in a transaction; the on-disk file move is performed *between* the DB
update and the commit so that if either step fails, the row reflects
reality after recovery (see `recovery.py`).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .models import ErrorKind, Photo, PhotoStatus, can_transition


SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    date_added TEXT NOT NULL,
    date_uploaded TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_timestamp TEXT,
    error_code TEXT,
    error_message TEXT,
    google_photos_id TEXT,
    file_hash TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    date_taken TEXT,
    camera_model TEXT,
    exif_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_hash ON photos(file_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_gphoto ON photos(google_photos_id)
    WHERE google_photos_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS upload_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_timestamp TEXT NOT NULL,
    completed_timestamp TEXT,
    photo_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS upload_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    batch_id INTEGER REFERENCES upload_batches(id),
    started_timestamp TEXT NOT NULL,
    completed_timestamp TEXT,
    status TEXT NOT NULL,
    error_code TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_attempts_photo ON upload_attempts(photo_id);

CREATE TABLE IF NOT EXISTS network_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    online INTEGER NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class Database:
    """Thread-safe SQLite wrapper.

    SQLite supports concurrent reads but serializes writes, which is fine
    for our workload (a couple of writers: file watcher and uploader).
    We use a single connection guarded by a lock — simpler than a pool,
    and the contention is minimal.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage transactions explicitly
            timeout=30.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    # -- photos ---------------------------------------------------------

    def insert_photo(self, photo: Photo) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                """
                INSERT INTO photos (
                    filename, filepath, status, date_added, date_uploaded,
                    attempt_count, last_attempt_timestamp, error_code,
                    error_message, google_photos_id, file_hash, file_size,
                    width, height, date_taken, camera_model, exif_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    photo.filename,
                    photo.filepath,
                    photo.status.value,
                    _iso(photo.date_added),
                    _iso(photo.date_uploaded),
                    photo.attempt_count,
                    _iso(photo.last_attempt_timestamp),
                    photo.error_code,
                    photo.error_message,
                    photo.google_photos_id,
                    photo.file_hash,
                    photo.file_size,
                    photo.width,
                    photo.height,
                    _iso(photo.date_taken),
                    photo.camera_model,
                    photo.exif_json,
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_photo(self, photo_id: int) -> Optional[Photo]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
        return _row_to_photo(row) if row else None

    def get_photo_by_path(self, path: str) -> Optional[Photo]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM photos WHERE filepath = ?", (path,)
            ).fetchone()
        return _row_to_photo(row) if row else None

    def get_photo_by_hash(self, file_hash: str) -> Optional[Photo]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM photos WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        return _row_to_photo(row) if row else None

    def photos_by_status(self, status: PhotoStatus) -> list[Photo]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM photos WHERE status = ? ORDER BY date_added DESC",
                (status.value,),
            ).fetchall()
        return [_row_to_photo(r) for r in rows]

    def status_counts(self) -> dict[PhotoStatus, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM photos GROUP BY status"
            ).fetchall()
        out = {s: 0 for s in PhotoStatus}
        for r in rows:
            out[PhotoStatus(r["status"])] = r["n"]
        return out

    def transition(
        self,
        photo_id: int,
        new_status: PhotoStatus,
        *,
        new_filepath: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        google_photos_id: Optional[str] = None,
        bump_attempt: bool = False,
        reset_attempts: bool = False,
        mark_uploaded: bool = False,
    ) -> Photo:
        """Atomic state transition. Raises if the transition is illegal."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"photo {photo_id} not found")
            current = PhotoStatus(row["status"])
            if current != new_status and not can_transition(current, new_status):
                raise ValueError(
                    f"illegal transition {current.value} -> {new_status.value}"
                )

            fields = ["status = ?", "last_attempt_timestamp = ?"]
            params: list = [new_status.value, _iso(datetime.utcnow())]

            if new_filepath is not None:
                fields.append("filepath = ?")
                params.append(new_filepath)
            if error_code is not None:
                fields.append("error_code = ?")
                params.append(error_code)
            if error_message is not None:
                fields.append("error_message = ?")
                params.append(error_message)
            if google_photos_id is not None:
                fields.append("google_photos_id = ?")
                params.append(google_photos_id)
            if bump_attempt:
                fields.append("attempt_count = attempt_count + 1")
            if reset_attempts:
                fields.append("attempt_count = 0")
                fields.append("error_code = NULL")
                fields.append("error_message = NULL")
            if mark_uploaded:
                fields.append("date_uploaded = ?")
                params.append(_iso(datetime.utcnow()))

            params.append(photo_id)
            conn.execute(
                f"UPDATE photos SET {', '.join(fields)} WHERE id = ?", params
            )
            row = conn.execute(
                "SELECT * FROM photos WHERE id = ?", (photo_id,)
            ).fetchone()
        return _row_to_photo(row)

    def delete_photo(self, photo_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))

    # -- upload batches / attempts -------------------------------------

    def start_batch(self, photo_count: int) -> int:
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO upload_batches (created_timestamp, photo_count, status)"
                " VALUES (?, ?, 'running')",
                (_iso(datetime.utcnow()), photo_count),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def finish_batch(self, batch_id: int, success: int, failure: int) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE upload_batches SET completed_timestamp = ?, "
                "success_count = ?, failure_count = ?, status = 'done' "
                "WHERE id = ?",
                (_iso(datetime.utcnow()), success, failure, batch_id),
            )

    def record_attempt(
        self,
        photo_id: int,
        batch_id: Optional[int],
        status: str,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO upload_attempts (photo_id, batch_id, started_timestamp, "
                "completed_timestamp, status, error_code, error_message) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    photo_id,
                    batch_id,
                    _iso(datetime.utcnow()),
                    _iso(datetime.utcnow()),
                    status,
                    error_code,
                    error_message,
                ),
            )

    def log_network(self, online: bool, note: str = "") -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO network_log (timestamp, online, note) VALUES (?, ?, ?)",
                (_iso(datetime.utcnow()), 1 if online else 0, note),
            )

    # -- settings -------------------------------------------------------

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _row_to_photo(row: sqlite3.Row) -> Photo:
    return Photo(
        id=row["id"],
        filename=row["filename"],
        filepath=row["filepath"],
        status=PhotoStatus(row["status"]),
        date_added=_parse(row["date_added"]) or datetime.utcnow(),
        date_uploaded=_parse(row["date_uploaded"]),
        attempt_count=row["attempt_count"],
        last_attempt_timestamp=_parse(row["last_attempt_timestamp"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        google_photos_id=row["google_photos_id"],
        file_hash=row["file_hash"],
        file_size=row["file_size"],
        width=row["width"],
        height=row["height"],
        date_taken=_parse(row["date_taken"]),
        camera_model=row["camera_model"],
        exif_json=row["exif_json"],
    )
