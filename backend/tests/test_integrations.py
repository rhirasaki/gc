"""Drive + Places integrations, tested through injected fake transports —
no credentials, no network."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.integrations.drive import DriveClient
from app.integrations.places import PlacesClient
from app.models import MapPin
from app.services.pin_enrich import enrich_pins

from test_pipeline_units import _seed


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    yield s
    s.close()


def _drive_fake(pages):
    """Fake transport: paginated file listing + media downloads + creates."""
    calls = []

    def transport(url, *, method="GET", data=None, headers=None):
        calls.append((method, url))
        if "alt=media" in url:
            return b"JPEGDATA"
        if method == "POST" and "uploadType=multipart" in url:
            return json.dumps({"id": "up1"}).encode()
        if method == "POST":
            return json.dumps({"id": "newfolder"}).encode()
        if "pageToken=tok2" in url:
            return json.dumps(pages[1]).encode()
        return json.dumps(pages[0]).encode()

    transport.calls = calls
    return transport


def test_drive_list_paginates():
    t = _drive_fake([
        {"files": [{"id": "a", "name": "one.jpg", "mimeType": "image/jpeg", "size": "10"}],
         "nextPageToken": "tok2"},
        {"files": [{"id": "b", "name": "two.kml", "mimeType": "application/vnd", "size": "5"}]},
    ])
    files = DriveClient(t).list_folder("folder1")
    assert [f.id for f in files] == ["a", "b"]
    assert files[0].size == 10


def test_drive_download_and_upload(tmp_path):
    t = _drive_fake([{"files": []}])
    c = DriveClient(t)
    dest = c.download("a", tmp_path / "sub" / "one.jpg")
    assert dest.read_bytes() == b"JPEGDATA"
    local = tmp_path / "book.pdf"
    local.write_bytes(b"%PDF")
    assert c.upload(local, "parent1") == "up1"
    # multipart body carried both metadata and content
    method, url = t.calls[-1]
    assert method == "POST" and "uploadType=multipart" in url


def test_drive_ensure_folder_finds_existing():
    def transport(url, *, method="GET", data=None, headers=None):
        return json.dumps({"files": [{"id": "existing"}]}).encode()

    assert DriveClient(transport).ensure_folder("Rendered", "root") == "existing"


def _places_fake(response):
    def transport(body):
        transport.last = json.loads(body)
        return json.dumps(response).encode()

    return transport


def test_places_search_parses_hit():
    t = _places_fake({"places": [{
        "displayName": {"text": "Blue Lagoon"},
        "primaryType": "spa",
        "location": {"latitude": 63.88, "longitude": -22.45},
        "formattedAddress": "Grindavik, Iceland"}]})
    hit = PlacesClient(t).search("blue lagoon", near=(63.9, -22.4))
    assert hit.category == "spa" and hit.lat == pytest.approx(63.88)
    assert t.last["locationBias"]["circle"]["center"]["latitude"] == 63.9


def test_places_search_no_results():
    assert PlacesClient(_places_fake({})).search("nowhere") is None


def test_enrich_pins_fills_only_missing(db):
    p, _, _ = _seed(db)
    incomplete = MapPin(project_id=p.id, place_name="Blue Lagoon", source="kml")
    complete = MapPin(project_id=p.id, place_name="Skogafoss", category="waterfall",
                      lat=63.53, lng=-19.51, source="kml")
    db.add_all([incomplete, complete])
    db.commit()
    db.refresh(p)

    t = _places_fake({"places": [{
        "displayName": {"text": "Blue Lagoon"}, "primaryType": "spa",
        "location": {"latitude": 63.88, "longitude": -22.45},
        "formattedAddress": "Grindavik"}]})
    r = enrich_pins(db, p, client=PlacesClient(t))
    assert r == {"enriched": 1, "already_complete": 1, "not_found": 0}
    assert incomplete.category == "spa" and incomplete.lat == pytest.approx(63.88)
    assert complete.category == "waterfall"  # human/complete data untouched
    assert incomplete.raw_metadata["places_enrichment"]["address"] == "Grindavik"


def test_drive_pull_round_trip(db, tmp_path, monkeypatch):
    """Pull: fake Drive folder with a photo + a note + a KML -> local inbox ->
    the same import pipeline as local folders."""
    from PIL import Image

    from app.config import settings
    from app.integrations.drive import DriveFile
    from app.services.drive_sync import pull_from_drive

    monkeypatch.setattr(settings, "data_root", tmp_path)
    p, _, _ = _seed(db)
    p.drive_folder_id = "folder123"
    db.commit()

    class FakeDrive:
        def list_folder(self, folder_id):
            assert folder_id == "folder123"
            return [DriveFile("f1", "beach.jpg", "image/jpeg", 100),
                    DriveFile("f2", "day1.txt", "text/plain", 20),
                    DriveFile("f3", "places.kml", "application/vnd", 30)]

        def download(self, file_id, dest):
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.suffix == ".jpg":
                Image.new("RGB", (400, 300), "#336699").save(dest)
            elif dest.suffix == ".txt":
                dest.write_text("Day 1: harbor walk")
            else:
                dest.write_text("<kml><Document><Placemark><name>Harbor</name>"
                                "<Point><coordinates>-21.9,64.1,0</coordinates></Point>"
                                "</Placemark></Document></kml>")
            return dest

    r = pull_from_drive(db, p, client=FakeDrive())
    assert r["photos"] == 1 and r["notes"] == 1 and r["pins"] == 1
    assert any(pin.place_name == "Harbor" for pin in p.map_pins)


def test_drive_pull_requires_folder(db):
    from app.services.drive_sync import pull_from_drive

    p, _, _ = _seed(db)
    with pytest.raises(ValueError):
        pull_from_drive(db, p, client=object())
