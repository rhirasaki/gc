"""Database-level tests: CRUD, transitions, illegal transitions, dedup."""

from datetime import datetime

import pytest

from photo_manager.database import Database
from photo_manager.models import Photo, PhotoStatus


def _make_photo(filepath="/tmp/p.jpg", file_hash="h1", status=PhotoStatus.INBOX):
    return Photo(
        id=None, filename="p.jpg", filepath=filepath, status=status,
        date_added=datetime.utcnow(), file_hash=file_hash, file_size=1024,
    )


def test_insert_and_fetch(tmp_path):
    db = Database(tmp_path / "x.db")
    pid = db.insert_photo(_make_photo())
    fetched = db.get_photo(pid)
    assert fetched is not None
    assert fetched.status == PhotoStatus.INBOX


def test_transition_inbox_to_pending(tmp_path):
    db = Database(tmp_path / "x.db")
    pid = db.insert_photo(_make_photo())
    p = db.transition(pid, PhotoStatus.PENDING, new_filepath="/tmp/pending/p.jpg")
    assert p.status == PhotoStatus.PENDING
    assert p.filepath == "/tmp/pending/p.jpg"


def test_illegal_transition_rejected(tmp_path):
    db = Database(tmp_path / "x.db")
    pid = db.insert_photo(_make_photo())
    with pytest.raises(ValueError):
        db.transition(pid, PhotoStatus.UPLOADED)


def test_bump_and_reset_attempts(tmp_path):
    db = Database(tmp_path / "x.db")
    pid = db.insert_photo(_make_photo())
    db.transition(pid, PhotoStatus.PENDING)
    db.transition(pid, PhotoStatus.UPLOADING)
    db.transition(pid, PhotoStatus.PENDING, bump_attempt=True)
    assert db.get_photo(pid).attempt_count == 1
    db.transition(pid, PhotoStatus.UPLOADING)
    db.transition(pid, PhotoStatus.PENDING, bump_attempt=True)
    assert db.get_photo(pid).attempt_count == 2
    db.transition(pid, PhotoStatus.UPLOADING)
    db.transition(pid, PhotoStatus.UPLOADED, mark_uploaded=True, reset_attempts=True)
    p = db.get_photo(pid)
    assert p.attempt_count == 0
    assert p.date_uploaded is not None


def test_get_by_hash(tmp_path):
    db = Database(tmp_path / "x.db")
    db.insert_photo(_make_photo(file_hash="abc"))
    found = db.get_photo_by_hash("abc")
    assert found is not None and found.file_hash == "abc"


def test_status_counts(tmp_path):
    db = Database(tmp_path / "x.db")
    db.insert_photo(_make_photo(filepath="/a", file_hash="1"))
    db.insert_photo(_make_photo(filepath="/b", file_hash="2"))
    counts = db.status_counts()
    assert counts[PhotoStatus.INBOX] == 2
