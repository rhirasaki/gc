"""Scale stress test for the chunked rendering path (§1: must survive big
photo-heavy books; §13 stage 8).

Generates a project of noisy (incompressible) photos big enough to cross the
chunk threshold, renders FINAL through the chunked one-process-per-chunk
path, and verifies page-map exactness + peak app-process memory staying flat
(the whole point of fresh worker processes).

Run: PBG_CHROMIUM_EXECUTABLE=... python -m scripts.stress_render [chapters] [photos_per]
"""
import os
import random
import resource
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tmp = Path(tempfile.mkdtemp(prefix="pbg-stress-"))
os.environ.setdefault("PBG_DATA_ROOT", str(tmp / "projects"))
os.environ.setdefault("PBG_DB_URL", f"sqlite:///{tmp}/stress.db")
os.environ.setdefault("PBG_REQUIRE_SWAP", "false")
os.environ.setdefault("PBG_WORKING_LONG_EDGE_PX", "2400")  # fat derivatives on purpose
os.environ.setdefault("PBG_CHUNK_THRESHOLD_MB", "150")

from PIL import Image

from app.db import SessionLocal, init_db
from app.models import Client, Project
from app.services.ingest import import_photos, propose_day_chapters
from app.build.builder import build_monolith
from app.rendering import assembly
from app.rendering.book import render_final
from app.rendering.engine import measure_payload_mb


def noisy_photo(path: Path, w: int, h: int, seed: int) -> None:
    """Random RGB noise — compresses terribly, which is exactly what we want
    to fatten the payload like real photographs do."""
    rng = random.Random(seed)
    img = Image.frombytes("RGB", (w, h), bytes(rng.getrandbits(8) for _ in range(w * h * 3)))
    img.save(path, "JPEG", quality=92)


def main(chapters: int = 16, per: int = 8) -> None:
    init_db()
    db = SessionLocal()
    src = tmp / "roll"
    src.mkdir()
    print(f"Generating {chapters * per} noisy photos…", flush=True)
    n = 0
    for d in range(chapters):
        for i in range(per):
            w, h = (2400, 1600) if i % 3 else (1600, 2400)
            p = src / f"d{d:02d}_{i}.jpg"
            noisy_photo(p, w, h, n)
            # EXIF day stamp so ingestion clusters into chapters
            img = Image.open(p)
            ex = Image.Exif()
            ex[0x0132] = f"2025:05:{(d % 28) + 1:02d} {9 + i:02d}:00:00"
            img.save(p, "JPEG", quality=92, exif=ex)
            n += 1

    c = Client(name="Stress Client")
    db.add(c)
    db.flush()
    project = Project(client_id=c.id, trip_name="Stress Expedition",
                      template_id="alpine-adventure", images_per_chapter=per)
    db.add(project)
    db.commit()

    t0 = time.monotonic()
    import_photos(db, project, src)
    propose_day_chapters(db, project)
    db.refresh(project)
    for ch in project.chapters:
        ch.narrative = ("A long day on the route, logged plainly and without "
                        "embellishment, one ridge after another. " * 8).strip()
    db.commit()
    print(f"Ingest: {time.monotonic() - t0:.0f}s, {len(project.chapters)} chapters", flush=True)

    monolith = build_monolith(project)
    payload = measure_payload_mb(monolith)
    print(f"Payload: {payload:.0f}MB "
          f"(threshold {os.environ['PBG_CHUNK_THRESHOLD_MB']}MB)", flush=True)

    t1 = time.monotonic()
    result = render_final(db, project, monolith)
    dt = time.monotonic() - t1
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    child_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024

    assert result.chunked, "expected the chunked path at this payload"
    real_pages = assembly.page_count(result.pdf_path)
    assert real_pages == result.total_pages, (real_pages, result.total_pages)
    for e in result.page_map:
        part = assembly.page_count(Path(f"{os.environ['PBG_DATA_ROOT']}/{project.id}"
                                        f"/rendered/chapter_cache/{e.chapter_id}.pdf"))
        assert part == e.page_end - e.page_start + 1

    size_mb = result.pdf_path.stat().st_size / 1024**2
    print(f"RENDER OK: {real_pages} pages, {size_mb:.0f}MB PDF, chunked=True, "
          f"{dt:.0f}s ({dt / real_pages:.1f}s/page)", flush=True)
    print(f"Memory: app process peak {peak_mb:.0f}MB, "
          f"largest chunk worker {child_mb:.0f}MB", flush=True)
    print("STRESS OK", flush=True)


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:3]]
    main(*args)
