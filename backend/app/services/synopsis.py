"""Project synopsis: the short AI-written story summary on the dashboard card.
Cheap model, compact input (labels + excerpts, never whole chapters)."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..agents.runner import run_agent
from ..models import Project


def generate_synopsis(db: Session, project: Project) -> str:
    chapters = sorted(project.chapters, key=lambda c: c.position)
    payload = json.dumps({
        "trip_name": project.trip_name,
        "destinations": project.destinations,
        "occasion": project.trip_reason,
        "dates": [project.date_start.isoformat() if project.date_start else None,
                  project.date_end.isoformat() if project.date_end else None],
        "chapters": [{"label": c.label,
                      "excerpt": (c.narrative or "")[:200]} for c in chapters],
    }, ensure_ascii=False)
    result = run_agent(db, "synopsis", payload, project=project,
                       max_tokens=256, temperature=0.5)
    project.synopsis = result.get("synopsis", "")
    db.commit()
    return project.synopsis
