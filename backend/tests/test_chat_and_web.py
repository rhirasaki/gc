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
