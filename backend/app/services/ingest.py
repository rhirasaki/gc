"""Project ingestion service: photos in, derivatives out, assets rowed up,
day-clustered chapters proposed. All local, zero tokens (§5.4).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..ingestion import maps as maps_ing
from ..ingestion import notes as notes_ing
from ..models import Asset, Chapter, ChapterAsset, MapPin, Note, Project
from ..photos import pipeline
from ..rendering.book import project_dirs


def import_photos(db: Session, project: Project, source_dir: Path,
                  progress=lambda f, n: None) -> dict:
    dirs = project_dirs(project.id)
    files = sorted(p for p in source_dir.rglob("*") if p.suffix.lower() in pipeline.SUPPORTED_EXTS)
    imported = skipped = 0
    for i, f in enumerate(files):
        chash = pipeline.content_hash(f)
        if db.query(Asset).filter_by(project_id=project.id, content_hash=chash).first():
            skipped += 1
            continue
        original = dirs["originals"] / f.name
        if not original.exists():
            original.write_bytes(f.read_bytes())
        info = pipeline.analyze_original(original)
        working, w, h = pipeline.make_working_derivative(original, dirs["working"])
        exif = info["exif"]
        taken = datetime.fromisoformat(exif["taken_at"]) if exif.get("taken_at") else None
        gps = exif.get("gps") or {}
        db.add(Asset(
            project_id=project.id, original_path=str(original), working_path=str(working),
            content_hash=chash, perceptual_hash=info["perceptual_hash"],
            exif=exif, taken_at=taken, gps_lat=gps.get("lat"), gps_lng=gps.get("lng"),
            width=info["width"], height=info["height"], aspect_class=info["aspect_class"],
            blur_score=info["blur_score"],
        ))
        imported += 1
        if i % 10 == 0:
            db.commit()
            progress((i + 1) / max(len(files), 1), f"Imported {i + 1}/{len(files)}")
    db.commit()

    # Near-duplicate pass (local phash) — dupes never spend classification tokens.
    assets = db.query(Asset).filter_by(project_id=project.id).all()
    dupes = pipeline.find_near_duplicates(
        {a.id: a.perceptual_hash for a in assets if a.perceptual_hash})
    for aid, canonical in dupes.items():
        db.get(Asset, aid).duplicate_of = canonical
    db.commit()

    # Coastal/Tropical accent palette from the trip's own photos.
    project.sampled_palette = pipeline.sample_palette(
        [Path(a.working_path) for a in assets if a.working_path])
    db.commit()
    return {"imported": imported, "skipped_duplicates": skipped, "near_duplicates": len(dupes)}


def import_notes(db: Session, project: Project, paths: list[Path] | None = None,
                 pasted: str | None = None) -> int:
    normalized: list[notes_ing.NormalizedNote] = []
    for p in paths or []:
        normalized.extend(notes_ing.parse_any(p))
    if pasted:
        normalized.extend(notes_ing.parse_pasted(pasted))
    for n in normalized:
        db.add(Note(project_id=project.id, source_type=n.source_type, title=n.title,
                    text=n.text, noted_at=n.noted_at, raw_metadata=n.raw_metadata))
    db.commit()
    return len(normalized)


def import_map_pins(db: Session, project: Project, path: Path) -> int:
    pins = maps_ing.parse_any(path)
    for p in pins:
        db.add(MapPin(project_id=project.id, place_name=p.place_name, category=p.category,
                      lat=p.lat, lng=p.lng, visited_at=p.visited_at, source=p.source,
                      raw_metadata=p.raw_metadata))
    db.commit()
    return len(pins)


def propose_day_chapters(db: Session, project: Project, max_per_chapter: int | None = None) -> int:
    """Cluster photos into day chapters by EXIF date — the primary timeline
    signal (§2.1). Undated photos land in a final 'Unplaced' chapter."""
    max_per = max_per_chapter or project.images_per_chapter
    assets = [a for a in project.assets if a.duplicate_of is None]
    by_day: dict[str, list[Asset]] = {}
    undated: list[Asset] = []
    for a in assets:
        if a.taken_at:
            by_day.setdefault(a.taken_at.strftime("%Y-%m-%d"), []).append(a)
        else:
            undated.append(a)

    for ch in list(project.chapters):
        db.delete(ch)
    db.flush()

    pos = 0
    for day in sorted(by_day):
        photos = sorted(by_day[day], key=lambda a: a.taken_at)
        # Best photos first when trimming to the configured images-per-chapter.
        if len(photos) > max_per:
            photos = sorted(photos,
                            key=lambda a: -(a.classification or {}).get("quality_score", 0.5)
                            if a.classification else -0.5)[:max_per]
            photos = sorted(photos, key=lambda a: a.taken_at)
        label = datetime.strptime(day, "%Y-%m-%d").strftime("%B %d, %Y")
        ch = Chapter(project_id=project.id, position=pos, label=label)
        db.add(ch)
        db.flush()
        for i, a in enumerate(photos):
            db.add(ChapterAsset(chapter_id=ch.id, asset_id=a.id, position=i))
        pos += 1
    if undated:
        ch = Chapter(project_id=project.id, position=pos, label="More Moments")
        db.add(ch)
        db.flush()
        for i, a in enumerate(undated[:max_per]):
            db.add(ChapterAsset(chapter_id=ch.id, asset_id=a.id, position=i))
        pos += 1
    db.commit()
    return pos
