"""Folder layout and atomic moves."""

from pathlib import Path

from photo_manager.folders import LibraryLayout, move_file
from photo_manager.models import PhotoStatus


def test_ensure_creates_all_subdirs(tmp_path):
    layout = LibraryLayout(tmp_path / "lib")
    layout.ensure()
    for s in PhotoStatus:
        assert layout.dir_for(s).parent.exists() or layout.dir_for(s).exists()


def test_uploaded_dir_is_dated(tmp_path):
    from datetime import date
    layout = LibraryLayout(tmp_path / "lib")
    layout.ensure()
    d = layout.dir_for(PhotoStatus.UPLOADED, when=date(2026, 5, 17))
    assert d.name == "2026-05-17"


def test_move_file_basic(tmp_path):
    src = tmp_path / "src.jpg"
    src.write_bytes(b"data")
    dst = tmp_path / "dst"
    final = move_file(src, dst)
    assert final.exists()
    assert not src.exists()


def test_move_file_disambiguates(tmp_path):
    src1 = tmp_path / "a.jpg"; src1.write_bytes(b"1")
    src2 = tmp_path / "b" / "a.jpg"; src2.parent.mkdir(); src2.write_bytes(b"2")
    dst = tmp_path / "dst"
    move_file(src1, dst)
    final = move_file(src2, dst)
    assert final.name == "a (1).jpg"
    assert final.read_bytes() == b"2"
