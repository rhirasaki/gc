"""Google Maps list ingestion: KML / GeoJSON exports (and a Places API hook).

Produces normalized MapPin dicts; downstream never sees format-specific data.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class NormalizedPin:
    place_name: str
    category: str | None = None
    lat: float | None = None
    lng: float | None = None
    visited_at: datetime | None = None
    source: str = "kml"
    raw_metadata: dict | None = None


_PLACEMARK_RE = re.compile(r"<Placemark>(.*?)</Placemark>", re.S)
_NAME_RE = re.compile(r"<name>(.*?)</name>", re.S)
_COORD_RE = re.compile(r"<coordinates>\s*([-\d.]+),([-\d.]+)", re.S)
_DESC_RE = re.compile(r"<description>(.*?)</description>", re.S)


def parse_kml(path: Path) -> list[NormalizedPin]:
    """Google Takeout 'Saved Places' KML. Regex over placemarks keeps this
    dependency-free; KML from Takeout is machine-generated and regular."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pins: list[NormalizedPin] = []
    for m in _PLACEMARK_RE.finditer(text):
        block = m.group(1)
        name = _NAME_RE.search(block)
        coord = _COORD_RE.search(block)
        desc = _DESC_RE.search(block)
        pins.append(NormalizedPin(
            place_name=(name.group(1).strip() if name else "Unnamed place"),
            lng=float(coord.group(1)) if coord else None,
            lat=float(coord.group(2)) if coord else None,
            source="kml",
            raw_metadata={"description": desc.group(1).strip()[:1000]} if desc else None,
        ))
    return pins


def parse_geojson(path: Path) -> list[NormalizedPin]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pins: list[NormalizedPin] = []
    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}
        coords = geom.get("coordinates") or [None, None]
        loc = props.get("location", {}) or {}
        visited = None
        if props.get("date"):
            try:
                visited = datetime.fromisoformat(props["date"].replace("Z", "+00:00"))
            except ValueError:
                pass
        pins.append(NormalizedPin(
            place_name=loc.get("name") or props.get("name") or "Unnamed place",
            category=loc.get("category") or props.get("category"),
            lng=coords[0], lat=coords[1],
            visited_at=visited, source="geojson", raw_metadata=props,
        ))
    return pins


def parse_any(path: Path) -> list[NormalizedPin]:
    ext = path.suffix.lower()
    if ext == ".kml":
        return parse_kml(path)
    if ext in (".geojson", ".json"):
        return parse_geojson(path)
    raise ValueError(f"Unsupported map export format: {ext}")


# Google Maps *lists* expose no public API — KML/GeoJSON export (above) is the
# ingestion path. Enrichment of imported pins via the Places API lives in
# app/integrations/places.py + services/pin_enrich.py.
