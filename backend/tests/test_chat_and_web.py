"""Units for the chat pick flow and the web preview build."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.chat.orchestrator import _pick_candidates
from app.models import Asset, Chapter, ChapterAsset, Client, Project

from test_pipeline_units import _seed  # same seeding helper


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()


def test_pick_candidates_ranks_by_criteria(db):
    p, ch, _ = _seed(db)
    wide = Asset(project_id=p.id, original_path="/x/wide.jpg", aspect_class="16:9",
                 classification={"quality_score": 0.5, "subjects": ["beach"]})
    tall = Asset(project_id=p.id, original_path="/x/tall.jpg", aspect_class="portrait-tall",
                 classification={"quality_score": 0.9, "subjects": ["church"]})
    db.add_all([wide, tall])
    db.commit()
    db.refresh(p)

    r = _pick_candidates(p, {"chapter_id": ch.id, "position": 2, "criteria": "a wider shot"})
    assert r["kind"] == "pick" and r["position"] == 2
    ids = [c["id"] for c in r["candidates"]]
    # chapter's own photos are excluded; the wide unused photo outranks the
    # higher-quality tall one because the criteria says wider
    assert wide.id in ids and ids.index(wide.id) < ids.index(tall.id)
    in_chapter = {ca.asset_id for ca in ch.chapter_assets}
    assert not in_chapter.intersection(ids)


def test_pick_candidates_missing_chapter(db):
    p, _, _ = _seed(db)
    assert _pick_candidates(p, {"chapter_id": "nope", "position": 0})["kind"] == "error"


def test_web_preview_uses_api_urls(db, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "data_root", tmp_path)
    p, ch, assets = _seed(db)
    ch.narrative = "A day well spent."
    db.commit()
    from app.build.builder import build_web_preview

    out = build_web_preview(p)
    html = out.read_text()
    assert out.name == "book_web.html"
    assert f"/api/assets/{assets[0].id}/file" in html
    assert "file://" not in html  # web tier never leaks filesystem paths

    # and the print builder is unaffected afterwards
    from app.build import builder

    assert builder._IMG_MODE == "file"


def test_segment_notes_splits_and_supersedes(db, monkeypatch):
    from app.models import Note, NoteSource
    from app.services import segment

    p, _, _ = _seed(db)
    long_note = Note(project_id=p.id, source_type=NoteSource.pasted, title="Trip log",
                     text=("Day 1: landed and walked the harbor all morning. " * 3
                           + "Day 2: drove south the next morning to the beach. " * 3))
    short = Note(project_id=p.id, source_type=NoteSource.pasted, text="lobster soup")
    db.add_all([long_note, short])
    db.commit()
    db.refresh(p)

    def fake_agent(_db, name, payload, **kw):
        assert name == "ingestion"
        return {"segments": [
            {"day_hint": "Day 1", "text": "Day 1: landed and walked the harbor all morning."},
            {"day_hint": "Day 2", "text": "Day 2: drove south the next morning to the beach."},
        ], "mentions": [{"kind": "place", "phrase": "the harbor", "segment_index": 0}]}

    monkeypatch.setattr(segment, "run_agent", fake_agent)
    r = segment.segment_notes(db, p)
    assert r["notes_segmented"] == 1 and r["segments_created"] == 2
    db.refresh(p)
    segs = [n for n in p.notes_items if (n.raw_metadata or {}).get("segmented_from")]
    assert len(segs) == 2
    assert segs[0].raw_metadata["mentions"][0]["phrase"] == "the harbor"
    assert long_note.raw_metadata["superseded"] is True
    # short note untouched, and a second run doesn't re-spend on the original
    assert segment._looks_multi_day(short.text) is False
    assert segment.segment_notes(db, p)["notes_segmented"] == 0
