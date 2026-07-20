"""Chat orchestrator: cheap-model intent parsing over the compact manifest,
dispatching to the fixed tool vocabulary. Long-running tools become queued
jobs; instant tools run inline.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..agents.runner import run_agent
from ..jobs.queue import enqueue
from ..models import Project
from . import tools


INSTANT_TOOLS = {"swap_asset", "reorder_assets", "set_chapter_template",
                 "set_project_template", "undo_last"}
JOB_TOOLS = {"regenerate_narrative", "finalize_images", "render_preview",
             "render_final", "cleanup_artifacts"}


def handle_message(db: Session, project: Project, message: str) -> dict:
    manifest = tools.project_manifest(project)
    payload = json.dumps({"manifest": manifest, "request": message}, ensure_ascii=False)
    decision = run_agent(db, "chat_orchestrator", payload, project=project,
                         max_tokens=512, temperature=0.0)

    if "clarify" in decision:
        return {"kind": "clarify", "question": decision["clarify"],
                "options": decision.get("options", [])}
    if "answer" in decision:
        return {"kind": "answer", "text": decision["answer"]}

    tool, args = decision.get("tool"), decision.get("args", {})
    if tool == "swap_asset" and not args.get("new_asset_id"):
        return _pick_candidates(project, args)
    if tool in INSTANT_TOOLS:
        fn = getattr(tools, tool)
        result = fn(db, project, **args)
        return {"kind": "done", "tool": tool, "result": result,
                "confirmation": decision.get("confirmation", "")}
    if tool in JOB_TOOLS:
        job = enqueue(db, project.id, tool, args)
        return {"kind": "queued", "tool": tool, "job_id": job.id,
                "confirmation": decision.get("confirmation", "")}
    return {"kind": "error", "text": f"Unknown tool: {tool}"}


_WIDE = {"16:9", "pano", "3:2"}
_TALL = {"portrait", "portrait-tall"}


def _pick_candidates(project: Project, args: dict) -> dict:
    """Swap requested without a specific replacement: rank the project's
    unused photos against the stated criteria and let the human pick.
    Deterministic and token-free — the model's job ended at intent."""
    chapter = next((c for c in project.chapters if c.id == args.get("chapter_id")), None)
    if chapter is None:
        return {"kind": "error", "text": "That chapter no longer exists."}
    in_chapter = {ca.asset_id for ca in chapter.chapter_assets}
    criteria = (args.get("criteria") or "").lower()

    def score(a) -> float:
        cls = a.classification or {}
        s = float(cls.get("quality_score", 0.5))
        if ("wide" in criteria or "pano" in criteria) and a.aspect_class in _WIDE:
            s += 0.5
        if ("tall" in criteria or "portrait" in criteria) and a.aspect_class in _TALL:
            s += 0.5
        for word in criteria.split():
            if len(word) > 3 and word in " ".join(cls.get("subjects") or []).lower():
                s += 0.3
        return s

    pool = [a for a in project.assets
            if a.duplicate_of is None and a.id not in in_chapter]
    ranked = sorted(pool, key=score, reverse=True)[:8]
    return {
        "kind": "pick",
        "chapter_id": chapter.id,
        "position": int(args.get("position", 0)),
        "prompt": f"Pick the replacement for photo {int(args.get('position', 0)) + 1} in “{chapter.label}”:",
        "candidates": [{"id": a.id, "aspect": a.aspect_class,
                        "subjects": (a.classification or {}).get("subjects", [])}
                       for a in ranked],
    }
