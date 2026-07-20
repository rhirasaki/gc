"""Google Places API (New) — Text Search, used for pin ENRICHMENT.

Maps *lists* have no public API (which is why KML/GeoJSON export is the
ingestion path, per §2.1); what Places can do is corroborate and enrich what
we already have: canonical name, category (primaryType), exact coordinates,
formatted address. Requires GOOGLE_MAPS_API_KEY. Transport injectable for
tests.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Callable

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELDS = "places.displayName,places.primaryType,places.location,places.formattedAddress"


class PlacesNotConfigured(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("GOOGLE_MAPS_API_KEY"))


@dataclass
class PlaceHit:
    name: str
    category: str | None
    lat: float
    lng: float
    address: str | None


def _default_transport(body: bytes) -> bytes:
    if not configured():
        raise PlacesNotConfigured(
            "Places enrichment needs GOOGLE_MAPS_API_KEY in the environment.")
    req = urllib.request.Request(_SEARCH_URL, data=body, headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": _FIELDS,
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


class PlacesClient:
    def __init__(self, transport: Callable[[bytes], bytes] | None = None):
        self._t = transport or _default_transport

    def search(self, query: str, near: tuple[float, float] | None = None) -> PlaceHit | None:
        """Best text-search hit for a place name, optionally biased near a
        known coordinate (a pin's rough KML location)."""
        payload: dict = {"textQuery": query, "pageSize": 1}
        if near:
            payload["locationBias"] = {"circle": {
                "center": {"latitude": near[0], "longitude": near[1]},
                "radius": 50000.0}}
        data = json.loads(self._t(json.dumps(payload).encode()))
        places = data.get("places") or []
        if not places:
            return None
        p = places[0]
        loc = p.get("location", {})
        return PlaceHit(
            name=(p.get("displayName") or {}).get("text", query),
            category=p.get("primaryType"),
            lat=loc.get("latitude", 0.0), lng=loc.get("longitude", 0.0),
            address=p.get("formattedAddress"))
