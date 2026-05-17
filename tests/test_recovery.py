"""Crash-recovery tests: stranded UPLOADING rows are reconciled correctly."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from photo_manager.config import Config
from photo_manager.database import Database
from photo_manager.folders import LibraryLayout
from photo_manager.models import Photo, PhotoStatus
from photo_manager.recovery import recover_on_startup, sweep_stalled


class FakeClient:
    def __init__(self, exists_map=None):
        self.exists_map = exists_map or {}

    def media_item_exists(self, media_id, timeout=15.0):
        return bool(self.exists_map.get(media_id, False))


def _seed_uploading(db, layout, name, google_id=None) -> int:
    src = layout.dir_for(PhotoStatus.UPLOADING) / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"x")
    photo = Photo(
        id=None, filename=name, filepath=str(src),
        status=PhotoStatus.UPLOADING, date_added=datetime.utcnow(),
        google_photos_id=google_id, file_hash=name, file_size=1,
    )
    return db.insert_photo(photo)


@pytest.fixture
def setup(tmp_path):
    layout = LibraryLayout(tmp_path / "lib")
    layout.ensure()
    db = Database(tmp_path / "db.sqlite")
    cfg = Config(library_root=str(layout.root))
    return db, layout, cfg


def test_recovery_confirms_upload_visible_in_google(setup):
    db, layout, cfg = setup
    pid = _seed_uploading(db, layout, "confirmed.jpg", google_id="GID-1")
    client = FakeClient({"GID-1": True})
    summary = recover_on_startup(db, layout, client, cfg)
    assert summary["confirmed"] == 1
    p = db.get_photo(pid)
    assert p.status == PhotoStatus.UPLOADED
    assert "Uploaded" in p.filepath


def test_recovery_requeues_when_not_in_google(setup):
    db, layout, cfg = setup
    pid = _seed_uploading(db, layout, "lost.jpg", google_id="GID-2")
    client = FakeClient({})  # not in Google
    summary = recover_on_startup(db, layout, client, cfg)
    assert summary["requeued"] == 1
    p = db.get_photo(pid)
    assert p.status == PhotoStatus.PENDING
    assert p.attempt_count == 1
    assert "Pending" in p.filepath


def test_recovery_with_no_client_requeues(setup):
    db, layout, cfg = setup
    pid = _seed_uploading(db, layout, "noclient.jpg", google_id=None)
    summary = recover_on_startup(db, layout, None, cfg)
    assert summary["requeued"] == 1
    assert db.get_photo(pid).status == PhotoStatus.PENDING


def test_recovery_marks_lost_if_file_missing(setup):
    db, layout, cfg = setup
    pid = _seed_uploading(db, layout, "vanished.jpg")
    Path(db.get_photo(pid).filepath).unlink()
    summary = recover_on_startup(db, layout, None, cfg)
    assert summary["lost"] == 1
    assert db.get_photo(pid).status == PhotoStatus.FAILED


def test_sweep_stalled_resets_old_uploading(setup):
    db, layout, cfg = setup
    cfg.stalled_upload_grace_sec = 60
    pid = _seed_uploading(db, layout, "stalled.jpg")
    # Force last_attempt_timestamp into the distant past.
    old = (datetime.utcnow() - timedelta(hours=3)).isoformat()
    db._conn.execute("UPDATE photos SET last_attempt_timestamp = ? WHERE id = ?",
                      (old, pid))
    swept = sweep_stalled(db, layout, cfg)
    assert swept == 1
    assert db.get_photo(pid).status == PhotoStatus.PENDING
