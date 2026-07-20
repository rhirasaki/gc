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
