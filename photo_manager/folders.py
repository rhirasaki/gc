"""Folder structure management and atomic file moves.

The state machine in `models.PhotoStatus` maps one-to-one to a subfolder
under the library root. The on-disk move and the DB row are kept in sync
by `uploader.py`; this module just provides the primitives.
"""

from __future__ import annotations

import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .models import PhotoStatus


# Subfolder names, in lockstep with PhotoStatus values.
SUBDIRS = {
    PhotoStatus.INBOX: "Inbox",
    PhotoStatus.PENDING: "Pending",
    PhotoStatus.UPLOADING: "Uploading",
    PhotoStatus.UPLOADED: "Uploaded",
    PhotoStatus.FAILED: "Failed",
}
TEMP_SUBDIR = "Temp"


class LibraryLayout:
    """Owns the directory layout under a single library root."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in SUBDIRS.values():
            (self.root / sub).mkdir(exist_ok=True)
        (self.root / TEMP_SUBDIR).mkdir(exist_ok=True)

    def dir_for(self, status: PhotoStatus, when: Optional[date] = None) -> Path:
        sub = SUBDIRS[status]
        if status == PhotoStatus.UPLOADED:
            when = when or date.today()
            return self.root / sub / when.isoformat()
        return self.root / sub

    @property
    def temp_dir(self) -> Path:
        return self.root / TEMP_SUBDIR

    def cleanup_temp(self) -> None:
        if self.temp_dir.exists():
            for p in self.temp_dir.iterdir():
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                except OSError:
                    pass


def move_file(src: Path, dst_dir: Path, *, overwrite: bool = False) -> Path:
    """Move a file into dst_dir, returning the final path.

    The move is atomic on the same filesystem (rename). If we're crossing
    filesystems, falls back to copy + verify size + unlink so we never
    drop the source until the destination is durable.

    If the target name exists and overwrite is False, a numeric suffix is
    appended (`foo.jpg` -> `foo (1).jpg`).
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name
    if target.exists() and not overwrite:
        target = _disambiguate(target)

    try:
        os.replace(src, target)
        return target
    except OSError:
        # Cross-device move. Copy first, then verify, then unlink source.
        shutil.copy2(src, target)
        if target.stat().st_size != src.stat().st_size:
            target.unlink(missing_ok=True)
            raise IOError(f"size mismatch after copy: {src} -> {target}")
        src.unlink()
        return target


def _disambiguate(target: Path) -> Path:
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        candidate = target.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate
        i += 1
