"""Layout Agent's AI margin (§11): rank hero candidates for a chapter when
the operator asks. The deterministic selector stays authoritative for builds;
this is decision support for the pin-hero control, and only spends tokens
when the top candidates are genuinely close."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..agents.runner import run_agent
from ..layout.selector import _hero_score
from ..models import Chapter, Project

_CLOSE = 0.15  # score gap under which heuristics can't confidently decide


def suggest_hero(db: Session, project: Project, chapter: Chapter) -> dict:
    assets = [ca.asset for ca in chapter.chapter_assets
              if ca.asset_id != chapter.pinned_hero_asset_id]
    if not assets:
        return {"ranked": [], "rationale": "No photos in this chapter."}
    scored = sorted(assets, key=_hero_score, reverse=True)
    if len(scored) == 1 or _hero_score(scored[0]) - _hero_score(scored[1]) > _CLOSE:
        return {"ranked": [a.id for a in scored[:3]],
                "rationale": "Clear heuristic winner — no AI call needed."}

    top = scored[:5]
    payload = json.dumps({"candidates": [
        {"asset_id": a.id, "aspect": a.aspect_class, "blur_score": a.blur_score,
         "classification": {k: (a.classification or {}).get(k)
                            for k in ("subjects", "scene_type", "quality_score",
                                      "composition_notes", "suggested_role")}}
        for a in top]}, ensure_ascii=False)
    result = run_agent(db, "layout", payload, project=project,
                       chapter_id=chapter.id, max_tokens=512, temperature=0.0)
    valid = {a.id for a in top}
    ranked = [aid for aid in (result.get("ranked_asset_ids") or []) if aid in valid]
    if not ranked:
        ranked = [a.id for a in top]
    return {"ranked": ranked, "rationale": result.get("rationale", "")}
