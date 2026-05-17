"""EXIF extraction with HEIC support and graceful video fallback."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif",
                        ".tif", ".tiff", ".cr2", ".cr3", ".nef", ".arw",
                        ".dng", ".raf", ".orf", ".rw2"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".avi"}
ALL_SUPPORTED = SUPPORTED_IMAGE_EXTS | SUPPORTED_VIDEO_EXTS


@dataclass
class MediaInfo:
    width: Optional[int]
    height: Optional[int]
    date_taken: Optional[datetime]
    camera_model: Optional[str]
    exif_json: Optional[str]
    file_size: int
    file_hash: str


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in ALL_SUPPORTED


def hash_file(path: Path, chunk: int = 1 << 20) -> str:
    """SHA1 of file contents. Used for duplicate detection."""
    h = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def extract(path: Path) -> MediaInfo:
    size = path.stat().st_size
    file_hash = hash_file(path)

    ext = path.suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTS:
        return _extract_image(path, size, file_hash)
    return MediaInfo(
        width=None, height=None, date_taken=None, camera_model=None,
        exif_json=None, file_size=size, file_hash=file_hash,
    )


def _extract_image(path: Path, size: int, file_hash: str) -> MediaInfo:
    try:
        from PIL import ExifTags, Image
    except ImportError:
        log.warning("Pillow not installed; skipping EXIF for %s", path)
        return MediaInfo(None, None, None, None, None, size, file_hash)

    # Best-effort HEIC support.
    try:
        import pillow_heif  # type: ignore
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    width = height = None
    date_taken: Optional[datetime] = None
    camera: Optional[str] = None
    exif_dict: dict = {}

    try:
        with Image.open(path) as img:
            width, height = img.size
            raw_exif = img.getexif() if hasattr(img, "getexif") else None
            if raw_exif:
                tag_map = {v: k for k, v in ExifTags.TAGS.items()}
                for tag_id, value in raw_exif.items():
                    name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    exif_dict[name] = _safe(value)
                dt_str = raw_exif.get(tag_map.get("DateTimeOriginal", -1)) \
                    or raw_exif.get(tag_map.get("DateTime", -1))
                if isinstance(dt_str, str):
                    date_taken = _parse_exif_dt(dt_str)
                camera = exif_dict.get("Model") or exif_dict.get("Make")
    except Exception as e:
        log.debug("EXIF parse failed for %s: %s", path, e)

    return MediaInfo(
        width=width,
        height=height,
        date_taken=date_taken,
        camera_model=camera,
        exif_json=json.dumps(exif_dict, default=str) if exif_dict else None,
        file_size=size,
        file_hash=file_hash,
    )


def _safe(value):
    # EXIF can hand back bytes, IFDRational, etc. Coerce to JSON-friendly form.
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def _parse_exif_dt(s: str) -> Optional[datetime]:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
