"""Units: aspect classes, note normalization, KML parsing, layout selection,
manifest/undo tools against an in-memory DB."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db as dbmod
from app.db import Base
from app.ingestion.maps import parse_kml
from app.ingestion.notes import parse_google_keep_json, parse_pasted
from app.layout.selector import GRID_VARIANTS, plan_chapter_layout
from app.models import Asset, Chapter, ChapterAsset, Client, Project
from app.photos.pipeline import aspect_class
from app.chat import tools


@pytest.fixture()
def db(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


def _seed(db):
    c = Client(name="Test Client")
    db.add(c)
    db.flush()
    p = Project(client_id=c.id, trip_name="Iceland 2025")
    db.add(p)
    db.flush()
    ch = Chapter(project_id=p.id, position=0, label="Day One")
    db.add(ch)
    db.flush()
    assets = []
    specs = [("3:2", 3000, 2000, 0.9, "hero"), ("portrait", 2000, 2800, 0.6, "candid"),
             ("portrait", 2000, 2900, 0.5, "candid"), ("4:3", 2000, 1500, 0.7, "detail"),
             ("16:9", 3200, 1800, 0.4, "candid"), ("square", 2000, 2000, 0.65, "detail")]
    for i, (ac, w, h, q, role) in enumerate(specs):
        a = Asset(project_id=p.id, original_path=f"/x/{i}.jpg", aspect_class=ac,
                  width=w, height=h, blur_score=900,
                  classification={"quality_score": q, "suggested_role": role})
        db.add(a)
        db.flush()
        db.add(ChapterAsset(chapter_id=ch.id, asset_id=a.id, position=i))
        assets.append(a)
    db.commit()
    return p, ch, assets


def test_aspect_classes():
    assert aspect_class(3000, 2000) == "3:2"
    assert aspect_class(1600, 1600) == "square"
    assert aspect_class(1080, 1920) == "portrait-tall"
    assert aspect_class(4000, 1500) == "pano"
    assert aspect_class(4000, 3000) == "4:3"


def test_note_normalization(tmp_path):
    n = parse_pasted("Day 1: we landed in Reykjavik")[0]
    assert n.source_type.value == "pasted"
    keep = tmp_path / "k.json"
    keep.write_text('{"title":"Trip","textContent":"lobster soup",'
                    '"userEditedTimestampUsec": 1750000000000000}')
    k = parse_google_keep_json(keep)[0]
    assert k.title == "Trip" and "lobster" in k.text and k.noted_at is not None


def test_kml_parse(tmp_path):
    kml = tmp_path / "places.kml"
    kml.write_text("""<kml><Document>
      <Placemark><name>Blue Lagoon</name>
        <Point><coordinates>-22.4495,63.8804,0</coordinates></Point></Placemark>
      <Placemark><name>Hallgrimskirkja</name>
        <Point><coordinates>-21.9266,64.1417,0</coordinates></Point></Placemark>
    </Document></kml>""")
    pins = parse_kml(kml)
    assert len(pins) == 2
    assert pins[0].place_name == "Blue Lagoon"
    assert pins[0].lat == pytest.approx(63.8804)


def test_layout_plan_deterministic_and_constrained(db):
    _, ch, _ = _seed(db)
    plan1 = plan_chapter_layout(ch, narrative_words=400)
    plan2 = plan_chapter_layout(ch, narrative_words=400)
    assert [p.component for p in plan1] == [p.component for p in plan2]  # no randomness
    assert all(p.component in GRID_VARIANTS for p in plan1)
    assert plan1[0].component == "feature-clean"  # hero opens the chapter
    used = [a for p in plan1 for a in p.asset_ids]
    assert len(used) == len(set(used)) == 6  # every asset placed exactly once


def test_pinned_hero_escape_hatch(db):
    _, ch, assets = _seed(db)
    worst = assets[4]  # lowest quality
    ch.pinned_hero_asset_id = worst.id
    db.commit()
    plan = plan_chapter_layout(ch, narrative_words=100)
    assert plan[0].asset_ids == [worst.id]  # pin wins over auto-selection


def test_swap_and_undo(db):
    p, ch, assets = _seed(db)
    ch.changed_since_final = False
    db.commit()
    spare = Asset(project_id=p.id, original_path="/x/spare.jpg")
    db.add(spare)
    db.commit()
    tools.swap_asset(db, p, ch.id, 2, spare.id)
    assert ch.chapter_assets[2].asset_id == spare.id
    assert ch.changed_since_final  # exactly this chapter dirtied
    r = tools.undo_last(db, p)
    assert r["undone"] and ch.chapter_assets[2].asset_id == assets[2].id


def test_manifest_is_compact(db):
    p, ch, _ = _seed(db)
    m = tools.project_manifest(p)
    assert m["chapters"][0]["photos"] == 6
    assert "narrative" not in str(m)  # book content never enters chat context


def test_composition_score_prefers_thirds():
    from PIL import Image, ImageDraw

    from app.photos.pipeline import composition_score

    # Subject on the thirds intersection vs dead center vs empty frame
    def frame(cx_frac):
        img = Image.new("RGB", (600, 400), "#888888")
        d = ImageDraw.Draw(img)
        cx, cy = int(600 * cx_frac), int(400 / 3)
        d.ellipse([cx - 60, cy - 60, cx + 60, cy + 60], fill="#ffffff", outline="#000000", width=6)
        return img

    thirds = composition_score(frame(1 / 3))
    center = composition_score(frame(0.5))
    empty = composition_score(Image.new("RGB", (600, 400), "#888888"))
    assert 0.0 <= center <= 1.0 and 0.0 <= thirds <= 1.0
    assert thirds > center
    assert empty == 0.0


def test_map_spread_page_svg(db, tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from app.build.builder import map_spread_page
    from app.models import MapPin

    p, _, _ = _seed(db)
    assert map_spread_page(p) == ""  # <3 geolocated pins: no page
    for i, (name, lat, lng) in enumerate([("Harbor", 64.15, -21.94),
                                          ("Vik Beach", 63.41, -19.01),
                                          ("Lagoon", 64.05, -16.18)]):
        db.add(MapPin(project_id=p.id, place_name=name, lat=lat, lng=lng,
                      visited_at=datetime(2025, 6, 10 + i, tzinfo=timezone.utc)))
    db.commit()
    db.refresh(p)
    html = map_spread_page(p)
    assert html.count('class="page map-page"') == 1
    assert html.count("map-dot") == 3 and "Vik Beach" in html
    assert "map-route" in html  # timestamps present -> route line drawn
