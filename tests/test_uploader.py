"""End-to-end uploader behaviour with a fake Google Photos client.

Covers the spec's test scenarios:
  - happy path: photo moves Pending -> Uploaded
  - permanent failure (403): photo ends in /Failed with sidecar log, no retry
  - transient failure: photo moves back to Pending, attempt_count bumps
  - max retries: transient that exhausts retries lands in Failed
"""

from datetime import datetime
from pathlib import Path

import pytest

from photo_manager.config import Config
from photo_manager.database import Database
from photo_manager.folders import LibraryLayout, move_file
from photo_manager.google_photos import PhotosAPIError, UploadResult
from photo_manager.models import Photo, PhotoStatus
from photo_manager.uploader import UploadEngine


class FakeClient:
    def __init__(self, behavior=None):
        # behavior: list of (filename -> outcome). outcome can be:
        #   ("ok", "gphoto_id")
        #   ("http", status_code, message)
        #   ("exc", Exception)
        self.behavior = behavior or {}
        self.calls = []

    def upload_one(self, path, *, album_id=None, timeout=None):
        self.calls.append(path.name)
        spec = self.behavior.get(path.name, ("ok", f"GID-{path.name}"))
        kind = spec[0]
        if kind == "ok":
            return UploadResult(google_photos_id=spec[1])
        if kind == "http":
            raise PhotosAPIError(spec[1], spec[2])
        if kind == "exc":
            raise spec[1]
        raise AssertionError(f"bad spec {spec}")

    def media_item_exists(self, gid, timeout=15.0):
        return True


@pytest.fixture
def setup(tmp_path):
    layout = LibraryLayout(tmp_path / "lib")
    layout.ensure()
    db = Database(tmp_path / "db.sqlite")
    cfg = Config(library_root=str(layout.root), max_retries=3, batch_size=2,
                  per_file_timeout_sec=10)
    return db, layout, cfg


def _stage_pending(db, layout, name, content=b"data") -> int:
    src = layout.dir_for(PhotoStatus.PENDING) / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(content)
    photo = Photo(
        id=None, filename=name, filepath=str(src), status=PhotoStatus.PENDING,
        date_added=datetime.utcnow(), file_hash=name, file_size=len(content),
    )
    return db.insert_photo(photo)


def test_happy_path_moves_to_uploaded(setup):
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "ok.jpg")
    engine = UploadEngine(db, layout, FakeClient(), cfg)
    summary = engine.run_batch()
    assert summary == {"considered": 1, "success": 1, "failed": 0, "deferred": 0}

    p = db.get_photo(pid)
    assert p.status == PhotoStatus.UPLOADED
    assert p.google_photos_id == "GID-ok.jpg"
    assert "Uploaded" in p.filepath
    assert Path(p.filepath).exists()


def test_permanent_403_lands_in_failed(setup):
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "bad.jpg")
    client = FakeClient({"bad.jpg": ("http", 403, "forbidden")})
    engine = UploadEngine(db, layout, client, cfg)
    engine.run_batch()
    p = db.get_photo(pid)
    assert p.status == PhotoStatus.FAILED
    assert p.error_code == "HTTP_403"
    assert Path(p.filepath).exists()
    sidecar = Path(p.filepath).with_name(Path(p.filepath).stem + "_error.txt")
    assert sidecar.exists()
    assert "403" in sidecar.read_text()


def test_transient_503_requeues_and_bumps_attempt(setup):
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "flaky.jpg")
    client = FakeClient({"flaky.jpg": ("http", 503, "try later")})
    engine = UploadEngine(db, layout, client, cfg)
    engine.run_batch()
    p = db.get_photo(pid)
    assert p.status == PhotoStatus.PENDING
    assert p.attempt_count == 1
    assert p.error_code == "HTTP_503"
    assert "Pending" in p.filepath


def test_transient_after_max_retries_moves_to_failed(setup):
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "doomed.jpg")
    # Bump attempt_count up to max-1 so the next failure exhausts retries.
    db._conn.execute("UPDATE photos SET attempt_count = ? WHERE id = ?",
                      (cfg.max_retries - 1, pid))
    client = FakeClient({"doomed.jpg": ("http", 500, "fail")})
    engine = UploadEngine(db, layout, client, cfg)
    # Backoff would normally defer; force last_attempt_timestamp to None.
    db._conn.execute("UPDATE photos SET last_attempt_timestamp = NULL WHERE id = ?",
                      (pid,))
    engine.run_batch()
    p = db.get_photo(pid)
    assert p.status == PhotoStatus.FAILED


def test_backoff_defers_recent_failures(setup):
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "wait.jpg")
    db._conn.execute(
        "UPDATE photos SET attempt_count = 2, last_attempt_timestamp = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), pid),
    )
    engine = UploadEngine(db, layout, FakeClient(), cfg)
    summary = engine.run_batch()
    # Photo is not yet due, so the batch should consider zero.
    assert summary["considered"] == 0
    assert db.get_photo(pid).status == PhotoStatus.PENDING


def test_idempotency_uploaded_terminal(setup):
    """An UPLOADED photo cannot be re-uploaded or re-transitioned."""
    db, layout, cfg = setup
    pid = _stage_pending(db, layout, "done.jpg")
    engine = UploadEngine(db, layout, FakeClient(), cfg)
    engine.run_batch()
    # Now try to push it back through. Should raise.
    with pytest.raises(ValueError):
        db.transition(pid, PhotoStatus.PENDING)
