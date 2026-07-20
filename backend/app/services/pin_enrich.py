"""Pin enrichment via Places Text Search. Fills only what's missing or
clearly better — a pin's human-entered name is never overwritten, and pins the
user already edited keep their data (we only add category/coords/address when
absent)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..integrations.places import PlacesClient
from ..models import Project


def enrich_pins(db: Session, project: Project, progress=lambda f, n: None,
                client: PlacesClient | None = None) -> dict:
    client = client or PlacesClient()
    pins = project.map_pins
    enriched = skipped = misses = 0
    for i, pin in enumerate(pins):
        needs = pin.category is None or pin.lat is None or pin.lng is None
        if not needs:
            skipped += 1
            continue
        near = (pin.lat, pin.lng) if pin.lat is not None and pin.lng is not None else None
        hit = client.search(pin.place_name, near=near)
        if hit is None:
            misses += 1
            continue
        if pin.category is None:
            pin.category = hit.category
        if pin.lat is None or pin.lng is None:
            pin.lat, pin.lng = hit.lat, hit.lng
        meta = dict(pin.raw_metadata or {})
        meta.setdefault("places_enrichment", {
            "canonical_name": hit.name, "address": hit.address})
        pin.raw_metadata = meta
        enriched += 1
        progress((i + 1) / max(len(pins), 1), f"Enriched {pin.place_name}")
    db.commit()
    return {"enriched": enriched, "already_complete": skipped, "not_found": misses}
