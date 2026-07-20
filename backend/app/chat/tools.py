"""Structured chat tools (§9): the fixed vocabulary every chat request
resolves to. Each tool logs a ChangeLog row with undo state; content-touching
tools dirty exactly the chapters they touch.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Chapter, ChapterAsset, ChangeLog, Project


def _log(db: Session, project: Project, tool: str, args: dict,
         undo: dict | None = None, chapter_id: str | None = None,
         source: str = "chat") -> None:
    db.add(ChangeLog(project_id=project.id, chapter_id=chapter_id, tool=tool,
                     args=args, undo_state=undo, source=source))


def swap_asset(db: Session, project: Project, chapter_id: str, position: int,
               new_asset_id: str, source: str = "chat") -> dict:
    """Replace the asset at one position. Touches ONE link row + one dirty
    flag — the indexing guarantee from §4."""
    ca = (db.query(ChapterAsset)
          .filter_by(chapter_id=chapter_id, position=position).one_or_none())
    if ca is None:
        raise ValueError(f"No photo at position {position} in that chapter")
    undo = {"chapter_id": chapter_id, "position": position, "asset_id": ca.asset_id}
    ca.asset_id = new_asset_id
    chapter = db.get(Chapter, chapter_id)
    chapter.mark_dirty()
    _log(db, project, "swap_asset",
         {"chapter_id": chapter_id, "position": position, "new_asset_id": new_asset_id},
         undo, chapter_id, source)
    db.commit()
    return {"swapped": True, "chapter": chapter.label, "position": position}


def reorder_assets(db: Session, project: Project, chapter_id: str, order: list[str]) -> dict:
    chapter = db.get(Chapter, chapter_id)
    links = {ca.asset_id: ca for ca in chapter.chapter_assets}
    if set(order) != set(links):
        raise ValueError("Order list must contain exactly the chapter's current assets")
    undo = {"chapter_id": chapter_id,
            "order": [ca.asset_id for ca in sorted(chapter.chapter_assets, key=lambda c: c.position)]}
    # two-phase to dodge the unique (chapter_id, position) constraint
    for i, aid in enumerate(order):
        links[aid].position = 1000 + i
    db.flush()
    for i, aid in enumerate(order):
        links[aid].position = i
    chapter.mark_dirty()
    _log(db, project, "reorder_assets", {"chapter_id": chapter_id, "order": order}, undo, chapter_id)
    db.commit()
    return {"reordered": True, "chapter": chapter.label}


def set_chapter_template(db: Session, project: Project, chapter_id: str, variant: str) -> dict:
    chapter = db.get(Chapter, chapter_id)
    undo = {"chapter_id": chapter_id, "variant": chapter.template_variant_override}
    chapter.template_variant_override = variant
    chapter.mark_dirty()
    _log(db, project, "set_chapter_template", {"chapter_id": chapter_id, "variant": variant},
         undo, chapter_id)
    db.commit()
    return {"set": True, "chapter": chapter.label, "variant": variant}


def set_project_template(db: Session, project: Project, template_id: str) -> dict:
    undo = {"template_id": project.template_id}
    project.template_id = template_id
    for ch in project.chapters:
        ch.mark_dirty()
    _log(db, project, "set_project_template", {"template_id": template_id}, undo)
    db.commit()
    return {"set": True, "template": template_id}


def undo_last(db: Session, project: Project) -> dict:
    entry = (db.query(ChangeLog).filter_by(project_id=project.id)
             .filter(ChangeLog.tool != "undo_last")
             .order_by(ChangeLog.created_at.desc()).first())
    if entry is None or not entry.undo_state:
        return {"undone": False, "reason": "Nothing to undo"}
    u = entry.undo_state
    if entry.tool == "swap_asset":
        ca = (db.query(ChapterAsset)
              .filter_by(chapter_id=u["chapter_id"], position=u["position"]).one())
        ca.asset_id = u["asset_id"]
        db.get(Chapter, u["chapter_id"]).mark_dirty()
    elif entry.tool == "reorder_assets":
        chapter = db.get(Chapter, u["chapter_id"])
        links = {ca.asset_id: ca for ca in chapter.chapter_assets}
        for i, aid in enumerate(u["order"]):
            links[aid].position = 1000 + i
        db.flush()
        for i, aid in enumerate(u["order"]):
            links[aid].position = i
        chapter.mark_dirty()
    elif entry.tool == "set_chapter_template":
        ch = db.get(Chapter, u["chapter_id"])
        ch.template_variant_override = u["variant"]
        ch.mark_dirty()
    elif entry.tool == "set_project_template":
        project.template_id = u["template_id"]
        for ch in project.chapters:
            ch.mark_dirty()
    else:
        return {"undone": False, "reason": f"{entry.tool} is not undoable"}
    _log(db, project, "undo_last", {"undid": entry.tool})
    db.delete(entry)
    db.commit()
    return {"undone": True, "undid": entry.tool}


def project_manifest(project: Project) -> dict:
    """Compact state the orchestrator model sees — labels and ids, never book
    content. This is what keeps chat token-cheap."""
    return {
        "project": {"id": project.id, "trip": project.trip_name,
                    "template": project.template_id, "status": project.status.value},
        "chapters": [
            {"id": c.id, "position": c.position, "label": c.label,
             "photos": len(c.chapter_assets),
             "dirty": c.changed_since_final,
             "ungrounded": (c.grounding_report or {}).get("ungrounded_count", 0)}
            for c in sorted(project.chapters, key=lambda c: c.position)
        ],
    }
