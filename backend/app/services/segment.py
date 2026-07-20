"""Ingestion Agent wiring (§11): split multi-day notes into per-day Note rows
so chapter evidence lines up with the timeline. Extraction only — segment text
is preserved verbatim (the grounding pass depends on that), with the original
note kept in raw_metadata for audit.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..agents.runner import run_agent
from ..models import Note, Project

# Notes shorter than this, or with no day-boundary hints, aren't worth tokens.
_MIN_CHARS = 200
_HINTS = ("day ", "day-", "morning", "next ", "202")


def _looks_multi_day(text: str) -> bool:
    low = text.lower()
    return len(text) >= _MIN_CHARS and sum(low.count(h) for h in _HINTS) >= 2


def segment_notes(db: Session, project: Project, progress=lambda f, n: None) -> dict:
    candidates = [n for n in project.notes_items
                  if _looks_multi_day(n.text) and not (n.raw_metadata or {}).get("segmented")]
    segmented = created = 0
    for i, note in enumerate(candidates):
        result = run_agent(db, "ingestion", json.dumps({"note": note.text}, ensure_ascii=False),
                           project=project, max_tokens=4096, temperature=0.0)
        segments = result.get("segments") or []
        if len(segments) < 2:
            continue  # single segment: nothing gained, keep the original
        for seg in segments:
            db.add(Note(
                project_id=project.id, source_type=note.source_type,
                title=(f"{note.title} — {seg['day_hint']}" if note.title and seg.get("day_hint")
                       else seg.get("day_hint") or note.title),
                text=seg["text"], noted_at=note.noted_at,
                raw_metadata={"segmented_from": note.id,
                              "day_hint": seg.get("day_hint"),
                              "mentions": [m for m in (result.get("mentions") or [])
                                           if m.get("segment_index") == segments.index(seg)]},
            ))
            created += 1
        note.raw_metadata = {**(note.raw_metadata or {}), "segmented": True,
                             "superseded": True}
        segmented += 1
        progress((i + 1) / max(len(candidates), 1), f"Segmented {i + 1}/{len(candidates)} notes")
    db.commit()
    return {"notes_segmented": segmented, "segments_created": created,
            "skipped": len(project.notes_items) - segmented}
