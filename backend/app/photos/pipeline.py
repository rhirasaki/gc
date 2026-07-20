"""Photo pipeline (§5): ingest & derive, local-first analysis, finalize swap.

Everything in this module runs locally with zero token spend. AI is only
invoked later, by the Classification Agent, for what genuinely needs semantic
understanding — and even that is cached forever on content hash.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

try:  # HEIC support if the plugin is present
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from ..config import settings

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"}


def content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _to_degrees(value) -> float:
    d, m, s = value
    return float(d) + float(m) / 60 + float(s) / 3600


def extract_exif(img: Image.Image) -> dict:
    """Full EXIF as a JSON-safe dict, plus parsed gps/taken_at/camera keys."""
    raw = img.getexif()
    out: dict = {"tags": {}, "gps": None, "taken_at": None, "camera": None, "lens": None,
                 "orientation": raw.get(0x0112)}
    for tag_id, val in raw.items():
        name = TAGS.get(tag_id, str(tag_id))
        out["tags"][name] = str(val)[:500]
    try:
        gps_ifd = raw.get_ifd(0x8825)
        if gps_ifd:
            gps = {GPSTAGS.get(k, str(k)): v for k, v in gps_ifd.items()}
            if "GPSLatitude" in gps and "GPSLongitude" in gps:
                lat = _to_degrees(gps["GPSLatitude"])
                lng = _to_degrees(gps["GPSLongitude"])
                if gps.get("GPSLatitudeRef") == "S":
                    lat = -lat
                if gps.get("GPSLongitudeRef") == "W":
                    lng = -lng
                out["gps"] = {"lat": lat, "lng": lng}
    except (KeyError, ValueError, TypeError):
        pass
    exif_ifd = raw.get_ifd(0x8769)
    dt = exif_ifd.get(0x9003) or raw.get(0x0132)  # DateTimeOriginal, else DateTime
    if dt:
        try:
            out["taken_at"] = datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S").replace(
                tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    make, model = raw.get(0x010F), raw.get(0x0110)
    if make or model:
        out["camera"] = f"{make or ''} {model or ''}".strip()
    lens = exif_ifd.get(0xA434)
    if lens:
        out["lens"] = str(lens)
    return out


def aspect_class(width: int, height: int) -> str:
    """Bucket into the classes the layout selector understands."""
    if width == 0 or height == 0:
        return "unknown"
    r = width / height
    if r < 0.85:
        return "portrait-tall" if r < 0.7 else "portrait"
    if r < 1.15:
        return "square"
    if r < 1.45:
        return "4:3"
    if r < 1.65:
        return "3:2"
    return "16:9" if r < 2.0 else "pano"


def blur_score(img: Image.Image) -> float:
    """Variance of a Laplacian-ish edge response on a small grayscale copy.
    Higher = sharper. Cheap local heuristic; no AI."""
    g = ImageOps.grayscale(img.copy())
    g.thumbnail((256, 256))
    edges = g.filter(ImageFilter.FIND_EDGES)
    hist = edges.histogram()
    n = sum(hist)
    if n == 0:
        return 0.0
    mean = sum(i * c for i, c in enumerate(hist)) / n
    var = sum(c * (i - mean) ** 2 for i, c in enumerate(hist)) / n
    return round(var, 2)


def perceptual_hash(img: Image.Image) -> str:
    import imagehash

    return str(imagehash.phash(img))


def make_working_derivative(original: Path, working_dir: Path) -> tuple[Path, int, int]:
    """Screen-res derivative (long edge ~1600px) for all drafting. Originals
    are NEVER embedded in draft HTML — the reference project's core failure
    mode. Returns (path, orig_width, orig_height)."""
    working_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(original) as img:
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        out = working_dir / (original.stem + ".jpg")
        copy = img.copy()
        copy.thumbnail((settings.working_long_edge_px, settings.working_long_edge_px))
        if copy.mode not in ("RGB", "L"):
            copy = copy.convert("RGB")
        copy.save(out, "JPEG", quality=settings.derivative_quality, optimize=True)
    return out, w, h


def analyze_original(original: Path) -> dict:
    """One pass over the original: EXIF + dimensions + heuristics."""
    with Image.open(original) as img:
        exif = extract_exif(img)
        img_t = ImageOps.exif_transpose(img)
        w, h = img_t.size
        return {
            "exif": exif,
            "width": w,
            "height": h,
            "aspect_class": aspect_class(w, h),
            "blur_score": blur_score(img_t),
            "perceptual_hash": perceptual_hash(img_t),
        }


def find_near_duplicates(hashes: dict[str, str], max_distance: int | None = None) -> dict[str, str]:
    """asset_id -> duplicate_of asset_id for phash pairs within distance.
    First-seen wins as the canonical copy."""
    import imagehash

    max_distance = max_distance or settings.near_duplicate_phash_distance
    canonical: list[tuple[str, object]] = []
    dupes: dict[str, str] = {}
    for aid, hx in hashes.items():
        h = imagehash.hex_to_hash(hx)
        for cid, ch in canonical:
            if h - ch <= max_distance:
                dupes[aid] = cid
                break
        else:
            canonical.append((aid, h))
    return dupes


def sample_palette(image_paths: list[Path], colors: int = 5) -> list[str]:
    """Dominant colors across a project's photos, as hex strings. Feeds the
    Coastal/Tropical template's per-project accent tuning."""
    counts: dict[tuple[int, int, int], int] = {}
    for p in image_paths[:40]:
        try:
            with Image.open(p) as img:
                small = img.convert("RGB")
                small.thumbnail((64, 64))
                q = small.quantize(colors=8)
                pal = q.getpalette()
                for cnt, idx in q.getcolors() or []:
                    rgb = tuple(pal[idx * 3: idx * 3 + 3])
                    counts[rgb] = counts.get(rgb, 0) + cnt
        except OSError:
            continue
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:colors]
    return ["#%02x%02x%02x" % rgb for rgb, _ in top]
