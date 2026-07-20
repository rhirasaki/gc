"""End-to-end pipeline proof (build order stage 1+2, no AI calls):

synthetic trip photos -> ingest (EXIF, derivatives, phash) -> day chapters ->
monolith build -> FINAL render (Chromium) -> page map check ->
edit one chapter -> string-splice into monolith -> PREVIEW stitch from cache.

Run: python -m scripts.demo_e2e
"""
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

tmp = Path(tempfile.mkdtemp(prefix="pbg-demo-"))
os.environ["PBG_DATA_ROOT"] = str(tmp / "projects")
os.environ["PBG_DB_URL"] = f"sqlite:///{tmp}/demo.db"
os.environ["PBG_REQUIRE_SWAP"] = "false"

from PIL import Image, ImageDraw

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Chapter, Client, Project
from app.services.ingest import import_photos, import_notes, propose_day_chapters
from app.build.builder import build_monolith, rebuild_chapter
from app.rendering.book import render_final, stitch_preview
from app.rendering import assembly

PALETTE = ["#4a6b8a", "#8a6b4a", "#6b8a4a", "#8a4a6b", "#4a8a6b", "#6b4a8a"]


def make_demo_photos(dirpath: Path, days: int = 3, per_day: int = 6) -> None:
    dirpath.mkdir(parents=True)
    n = 0
    for d in range(days):
        for i in range(per_day):
            w, h = [(2400, 1600), (1600, 2400), (2000, 2000), (3200, 1400)][i % 4]
            img = Image.new("RGB", (w, h), PALETTE[n % len(PALETTE)])
            draw = ImageDraw.Draw(img)
            # Distinct geometry per photo so perceptual hashing doesn't
            # (correctly) collapse them as near-duplicates.
            rng = random.Random(n * 7919)
            for _ in range(14):
                x0, y0 = rng.randint(0, w - 200), rng.randint(0, h - 200)
                x1, y1 = x0 + rng.randint(100, w // 2), y0 + rng.randint(100, h // 2)
                shape = rng.choice(["rect", "ellipse", "line"])
                color = tuple(rng.randint(0, 255) for _ in range(3))
                if shape == "rect":
                    draw.rectangle([x0, y0, min(x1, w), min(y1, h)], fill=color)
                elif shape == "ellipse":
                    draw.ellipse([x0, y0, min(x1, w), min(y1, h)], fill=color)
                else:
                    draw.line([x0, y0, min(x1, w), min(y1, h)], fill=color, width=30)
            draw.text((60, 60), f"Day {d + 1} · Photo {i + 1}", fill="white")
            exif = Image.Exif()
            exif[0x0132] = f"2025:06:{10 + d:02d} {9 + i:02d}:30:00"
            img.save(dirpath / f"d{d}_{i}.jpg", exif=exif)
            n += 1


def main() -> None:
    init_db()
    db = SessionLocal()
    src = tmp / "camera_roll"
    make_demo_photos(src)

    client = Client(name="Demo Family")
    db.add(client)
    db.flush()
    project = Project(client_id=client.id, trip_name="Iceland, Together",
                      destinations=["Reykjavik", "Vik"], template_id="heritage-journal")
    db.add(project)
    db.commit()

    r = import_photos(db, project, src)
    print(f"imported: {r}")
    import_notes(db, project, pasted="Day 1: landed in Reykjavik, lobster soup at the harbor. "
                                     "Day 2: black sand beach at Vik. Day 3: northern lights!")
    n = propose_day_chapters(db, project)
    print(f"chapters: {n}")
    db.refresh(project)
    for ch in project.chapters:
        ch.narrative = ("The morning began the way the best ones do, without a plan. " * 6).strip()
    db.commit()

    monolith = build_monolith(project)
    print(f"monolith: {monolith} ({monolith.stat().st_size/1024:.0f}KB)")

    res = render_final(db, project, monolith)
    print(f"FINAL: {res.pdf_path} pages={res.total_pages} chunked={res.chunked} "
          f"payload={res.payload_mb:.1f}MB")
    assert res.total_pages == assembly.page_count(res.pdf_path)
    for e in res.page_map:
        print(f"  page_map {e.chapter_id[:8]}: {e.page_start}-{e.page_end}")

    # Edit chapter 2, splice by string, preview-stitch (only it re-renders).
    ch2 = sorted(project.chapters, key=lambda c: c.position)[1]
    ch2.narrative = "A completely rewritten day, twice as long. " * 24
    ch2.mark_dirty()
    db.commit()
    rebuild_chapter(project, ch2)
    preview = stitch_preview(db, project, monolith)
    print(f"PREVIEW: {preview} pages={assembly.page_count(preview)}")
    clean = [c for c in project.chapters if not c.changed_since_final]
    print(f"cached chapters reused: {len(clean)}/{len(project.chapters)}")
    print("E2E OK")


if __name__ == "__main__":
    main()
