"""Narrative generation + grounding QA (§6, §11).

Writer and checker are separate agents on separate calls — deliberately. The
writer emits evidence tags ([N1], [P2], [M3], [R4]); the grounding agent
verifies each sentence against the evidence content, and the report is stored
on the chapter for the review UI ("3 sentences aren't grounded — review
before finalizing"). Tags are stripped before layout.
"""
from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from ..models import Chapter, Project
from ..agents.runner import run_agent

_TAG_RE = re.compile(r"\s*\[[NPMR]\d+\]")


def build_evidence(project: Project, chapter: Chapter) -> tuple[list[dict], str]:
    """Compact evidence list with stable ids. Notes near the chapter's photo
    window are included; photos contribute EXIF-derived facts; pins contribute
    place facts."""
    evidence: list[dict] = []
    for i, note in enumerate(project.notes_items, 1):
        evidence.append({"id": f"N{i}", "kind": "note",
                         "text": note.text[:2000],
                         "when": note.noted_at.isoformat() if note.noted_at else None})
    for i, ca in enumerate(chapter.chapter_assets, 1):
        a = ca.asset
        facts = {"id": f"P{i}", "kind": "photo", "asset_id": a.id,
                 "taken_at": a.taken_at.isoformat() if a.taken_at else None,
                 "gps": {"lat": a.gps_lat, "lng": a.gps_lng} if a.gps_lat else None}
        if a.classification:
            facts["shows"] = a.classification.get("subjects")
            facts["scene"] = a.classification.get("scene_type")
        evidence.append(facts)
    for i, pin in enumerate(project.map_pins, 1):
        evidence.append({"id": f"M{i}", "kind": "map_pin", "place": pin.place_name,
                         "category": pin.category,
                         "visited_at": pin.visited_at.isoformat() if pin.visited_at else None})
    return evidence, json.dumps(evidence, ensure_ascii=False)


def strip_evidence_tags(text: str) -> str:
    return _TAG_RE.sub("", text)


def generate_chapter_narrative(db: Session, project: Project, chapter: Chapter, *,
                               tone: str | None = None, word_count: int = 350) -> dict:
    evidence, evidence_json = build_evidence(project, chapter)
    research = chapter.research_context or {}
    payload = json.dumps({
        "chapter_label": chapter.label,
        "tone": tone or chapter.narrative_tone or "warm, understated, specific",
        "approx_word_count": word_count,
        "EVIDENCE": json.loads(evidence_json),
        "RESEARCH": research.get("places", []),
    }, ensure_ascii=False)

    draft = run_agent(db, "narrative_writer", payload, project=project,
                      chapter_id=chapter.id, max_tokens=4096, temperature=0.7)

    # Second, cheaper adversarial pass: verify every sentence against evidence.
    qa_payload = json.dumps({"paragraphs": draft.get("paragraphs", []),
                             "evidence": evidence,
                             "research": research.get("places", [])}, ensure_ascii=False)
    report = run_agent(db, "grounding", qa_payload, project=project,
                       chapter_id=chapter.id, max_tokens=4096, temperature=0.0)

    chapter.narrative = "\n\n".join(strip_evidence_tags(p) for p in draft.get("paragraphs", []))
    chapter.narrative_tone = tone or chapter.narrative_tone
    chapter.grounding_report = report
    if draft.get("pull_quote"):
        chapter.layout_plan = {**(chapter.layout_plan or {}),
                               "pull_quote": strip_evidence_tags(draft["pull_quote"])}
    for ca in chapter.chapter_assets:
        cap = (draft.get("photo_captions") or {}).get(ca.asset_id)
        if cap:
            ca.caption = strip_evidence_tags(cap)
    chapter.mark_dirty()
    db.commit()
    return {"draft": draft, "grounding": report}


def research_places(db: Session, project: Project) -> dict:
    """Geo/History Research Agent over the project's pins + photo locations.
    Results are cached on each chapter that references the places."""
    places = [{"place": p.place_name, "category": p.category,
               "lat": p.lat, "lng": p.lng} for p in project.map_pins]
    if not places:
        return {"places": []}
    result = run_agent(db, "research", json.dumps({"places": places}, ensure_ascii=False),
                       project=project, max_tokens=4096, temperature=0.2)
    for chapter in project.chapters:
        chapter.research_context = result
    db.commit()
    return result
