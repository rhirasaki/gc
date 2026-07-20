"""API layer. One module, thin handlers — logic lives in services/."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..chat.orchestrator import handle_message
from ..config import settings
from ..db import get_db
from ..jobs.queue import enqueue
from ..models import (AIRun, Asset, Chapter, ChapterAsset, ChangeLog, Client,
                      Job, MapPin, Note, Project, ProjectStatus, Template)
from ..rendering.book import project_dirs
from ..services import ingest as ingest_svc

router = APIRouter(prefix="/api")


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


# ---------- clients ----------

class ClientIn(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    referral_source: str | None = None
    notes: str | None = None


@router.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "email": c.email,
             "projects": len(c.projects)} for c in db.query(Client).all()]


@router.post("/clients")
def create_client(body: ClientIn, db: Session = Depends(get_db)):
    c = Client(**body.model_dump())
    db.add(c)
    db.commit()
    return {"id": c.id}


# ---------- projects ----------

class ProjectIn(BaseModel):
    client_id: str
    trip_name: str
    destinations: list[str] = []
    date_start: datetime | None = None
    date_end: datetime | None = None
    trip_reason: str | None = None
    template_id: str | None = None
    input_path: str | None = None
    sale_price_usd: float = 2500.0
    images_per_chapter: int = 10


def _project_card(db: Session, p: Project) -> dict:
    spend = (db.query(func.coalesce(func.sum(AIRun.estimated_cost_usd), 0.0))
             .filter(AIRun.project_id == p.id).scalar())
    return {
        "id": p.id, "trip_name": p.trip_name, "client": p.client.name if p.client else None,
        "destinations": p.destinations, "status": p.status.value,
        "trip_reason": p.trip_reason,
        "date_start": p.date_start.isoformat() if p.date_start else None,
        "date_end": p.date_end.isoformat() if p.date_end else None,
        "template_id": p.template_id, "synopsis": p.synopsis,
        "photo_count": len([a for a in p.assets if a.duplicate_of is None]),
        "chapter_count": len(p.chapters),
        "ai_spend_usd": round(spend, 2), "sale_price_usd": p.sale_price_usd,
        "margin_pct": round(100 * (1 - spend / p.sale_price_usd), 1) if p.sale_price_usd else None,
    }


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    return [_project_card(db, p) for p in db.query(Project).all()]


@router.post("/projects")
def create_project(body: ProjectIn, db: Session = Depends(get_db)):
    p = Project(**body.model_dump())
    if not p.template_id:
        p.template_id = settings.default_template
    db.add(p)
    db.commit()
    project_dirs(p.id)
    return {"id": p.id}


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    card = _project_card(db, p)
    card["chapters"] = [
        {"id": c.id, "position": c.position, "label": c.label,
         "narrative": c.narrative, "dirty": c.changed_since_final,
         "page_start": c.page_start, "page_end": c.page_end,
         "grounding": c.grounding_report,
         "pinned_hero": c.pinned_hero_asset_id,
         "assets": [{"id": ca.asset_id, "position": ca.position, "caption": ca.caption}
                    for ca in c.chapter_assets]}
        for c in sorted(p.chapters, key=lambda c: c.position)]
    card["ai_overrides"] = p.ai_overrides
    return card


class StatusIn(BaseModel):
    status: ProjectStatus


@router.post("/projects/{project_id}/status")
def set_status(project_id: str, body: StatusIn, db: Session = Depends(get_db)):
    _get_project(db, project_id).status = body.status
    db.commit()
    return {"ok": True}


# ---------- ingestion ----------

@router.post("/projects/{project_id}/import/photos")
def import_photos(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    if not p.input_path or not Path(p.input_path).is_dir():
        raise HTTPException(400, "Project input_path is not a readable folder")
    result = ingest_svc.import_photos(db, p, Path(p.input_path))
    return result


class NotesIn(BaseModel):
    pasted: str | None = None
    file_paths: list[str] = []


@router.post("/projects/{project_id}/import/notes")
def import_notes(project_id: str, body: NotesIn, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    n = ingest_svc.import_notes(db, p, [Path(f) for f in body.file_paths], body.pasted)
    return {"imported": n}


class PinsIn(BaseModel):
    file_path: str


@router.post("/projects/{project_id}/import/pins")
def import_pins(project_id: str, body: PinsIn, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    return {"imported": ingest_svc.import_map_pins(db, p, Path(body.file_path))}


@router.post("/projects/{project_id}/chapters/propose")
def propose_chapters(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    return {"chapters": ingest_svc.propose_day_chapters(db, p)}


# ---------- assets ----------

@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    return [{"id": a.id, "original": a.original_path, "working": a.working_path,
             "aspect": a.aspect_class, "taken_at": a.taken_at.isoformat() if a.taken_at else None,
             "finalized": a.finalized, "duplicate_of": a.duplicate_of,
             "classification": a.classification, "role": a.suggested_role.value,
             "manual_override": a.manual_override, "blur_score": a.blur_score}
            for a in p.assets]


@router.get("/assets/{asset_id}/file")
def asset_file(asset_id: str, db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(404)
    path = a.working_path or a.original_path
    return FileResponse(path)


class AssetOverrideIn(BaseModel):
    classification: dict | None = None
    role: str | None = None


@router.post("/assets/{asset_id}/override")
def override_asset(asset_id: str, body: AssetOverrideIn, db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if a is None:
        raise HTTPException(404)
    if body.classification is not None:
        a.classification = body.classification
    if body.role:
        from ..models import AssetRole

        a.suggested_role = AssetRole(body.role)
    a.manual_override = True  # never clobbered by re-classification
    db.commit()
    return {"ok": True}


# ---------- chapter editing ----------

def _get_chapter(db: Session, project: Project, chapter_id: str) -> Chapter:
    ch = db.get(Chapter, chapter_id)
    if ch is None or ch.project_id != project.id:
        raise HTTPException(404, "Chapter not found in this project")
    return ch


class RenameIn(BaseModel):
    label: str


@router.post("/projects/{project_id}/chapters/{chapter_id}/rename")
def rename_chapter(project_id: str, chapter_id: str, body: RenameIn,
                   db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    ch = _get_chapter(db, p, chapter_id)
    old = ch.label
    ch.label = body.label
    ch.mark_dirty()
    db.add(ChangeLog(project_id=p.id, chapter_id=ch.id, tool="rename_chapter",
                     args={"label": body.label}, undo_state={"label": old}, source="ui"))
    db.commit()
    return {"ok": True}


class PinHeroIn(BaseModel):
    asset_id: str | None = None  # null unpins


@router.post("/projects/{project_id}/chapters/{chapter_id}/pin-hero")
def pin_hero(project_id: str, chapter_id: str, body: PinHeroIn,
             db: Session = Depends(get_db)):
    """The §8 escape hatch: a pinned hero wins over auto-selection outright."""
    p = _get_project(db, project_id)
    ch = _get_chapter(db, p, chapter_id)
    ch.pinned_hero_asset_id = body.asset_id
    ch.mark_dirty()
    db.commit()
    return {"ok": True, "pinned": body.asset_id}


class AddAssetIn(BaseModel):
    asset_id: str


@router.post("/projects/{project_id}/chapters/{chapter_id}/assets")
def add_chapter_asset(project_id: str, chapter_id: str, body: AddAssetIn,
                      db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    ch = _get_chapter(db, p, chapter_id)
    if any(ca.asset_id == body.asset_id for ca in ch.chapter_assets):
        raise HTTPException(400, "That photo is already in this chapter")
    pos = max((ca.position for ca in ch.chapter_assets), default=-1) + 1
    db.add(ChapterAsset(chapter_id=ch.id, asset_id=body.asset_id, position=pos))
    ch.mark_dirty()
    db.commit()
    return {"ok": True, "position": pos}


@router.delete("/projects/{project_id}/chapters/{chapter_id}/assets/{position}")
def remove_chapter_asset(project_id: str, chapter_id: str, position: int,
                         db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    ch = _get_chapter(db, p, chapter_id)
    target = next((ca for ca in ch.chapter_assets if ca.position == position), None)
    if target is None:
        raise HTTPException(404, "No photo at that position")
    removed_id = target.asset_id
    db.delete(target)
    db.flush()
    # close the gap so positions stay dense (two-phase for the unique constraint)
    rest = sorted((ca for ca in ch.chapter_assets if ca.position > position),
                  key=lambda ca: ca.position)
    for i, ca in enumerate(rest):
        ca.position = 1000 + i
    db.flush()
    for i, ca in enumerate(rest):
        ca.position = position + i
    if ch.pinned_hero_asset_id == removed_id:
        ch.pinned_hero_asset_id = None
    ch.mark_dirty()
    db.commit()
    return {"ok": True}


class ReorderIn(BaseModel):
    order: list[str]


@router.post("/projects/{project_id}/chapters/{chapter_id}/reorder")
def reorder_chapter(project_id: str, chapter_id: str, body: ReorderIn,
                    db: Session = Depends(get_db)):
    from ..chat import tools

    p = _get_project(db, project_id)
    _get_chapter(db, p, chapter_id)
    try:
        return tools.reorder_assets(db, p, chapter_id, body.order)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------- AI work (queued) ----------

@router.post("/projects/{project_id}/classify")
def classify(project_id: str, db: Session = Depends(get_db)):
    job = enqueue(db, project_id, "classify_batch")
    return {"job_id": job.id}


class NarrativeIn(BaseModel):
    chapter_id: str
    tone: str | None = None
    word_count: int = 350


@router.post("/projects/{project_id}/narrative")
def narrative(project_id: str, body: NarrativeIn, db: Session = Depends(get_db)):
    job = enqueue(db, project_id, "regenerate_narrative", body.model_dump())
    return {"job_id": job.id}


@router.post("/projects/{project_id}/research")
def research(project_id: str, db: Session = Depends(get_db)):
    from ..services.narrative import research_places

    p = _get_project(db, project_id)
    return research_places(db, p)


@router.post("/projects/{project_id}/synopsis")
def synopsis(project_id: str, db: Session = Depends(get_db)):
    from ..services.synopsis import generate_synopsis

    p = _get_project(db, project_id)
    return {"synopsis": generate_synopsis(db, p)}


@router.post("/projects/{project_id}/undo")
def undo(project_id: str, db: Session = Depends(get_db)):
    from ..chat.tools import undo_last

    p = _get_project(db, project_id)
    return undo_last(db, p)


class AIOverridesIn(BaseModel):
    ai_overrides: dict[str, dict]


@router.post("/projects/{project_id}/ai-overrides")
def set_ai_overrides(project_id: str, body: AIOverridesIn, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    p.ai_overrides = body.ai_overrides
    db.commit()
    return {"ok": True}


# ---------- file uploads (notes / map exports) ----------

@router.post("/projects/{project_id}/upload/notes")
async def upload_notes(project_id: str, files: list[UploadFile],
                       db: Session = Depends(get_db)):
    """Note files (Apple Notes .html, Keep .json, .docx, .txt/.md) uploaded
    straight from the browser — no filesystem paths for the operator."""
    p = _get_project(db, project_id)
    updir = project_dirs(p.id)["root"] / "uploads" / "notes"
    updir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for f in files:
        dest = updir / Path(f.filename or "note.txt").name
        dest.write_bytes(await f.read())
        saved.append(dest)
    try:
        n = ingest_svc.import_notes(db, p, saved)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"imported": n}


@router.post("/projects/{project_id}/upload/pins")
async def upload_pins(project_id: str, files: list[UploadFile],
                      db: Session = Depends(get_db)):
    """Google Takeout KML / GeoJSON uploads."""
    p = _get_project(db, project_id)
    updir = project_dirs(p.id)["root"] / "uploads" / "maps"
    updir.mkdir(parents=True, exist_ok=True)
    total = 0
    for f in files:
        dest = updir / Path(f.filename or "places.kml").name
        dest.write_bytes(await f.read())
        try:
            total += ingest_svc.import_map_pins(db, p, dest)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    return {"imported": total}


# ---------- rendering ----------

@router.post("/projects/{project_id}/render/{tier}")
def render(project_id: str, tier: str, db: Session = Depends(get_db)):
    if tier not in ("preview", "final"):
        raise HTTPException(400, "tier must be preview|final")
    job = enqueue(db, project_id, f"render_{tier}")
    return {"job_id": job.id}


@router.post("/projects/{project_id}/finalize-images")
def finalize(project_id: str, db: Session = Depends(get_db)):
    job = enqueue(db, project_id, "finalize_images")
    return {"job_id": job.id}


@router.post("/projects/{project_id}/cleanup")
def cleanup(project_id: str, db: Session = Depends(get_db)):
    job = enqueue(db, project_id, "cleanup_artifacts")
    return {"job_id": job.id}


class SwapIn(BaseModel):
    chapter_id: str
    position: int
    new_asset_id: str


@router.post("/projects/{project_id}/swap")
def swap(project_id: str, body: SwapIn, db: Session = Depends(get_db)):
    """Direct swap — completes the chat pick flow or a UI drag-replace."""
    from ..chat import tools

    p = _get_project(db, project_id)
    try:
        return tools.swap_asset(db, p, body.chapter_id, body.position,
                                body.new_asset_id, source="ui")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}/book/web")
def book_web(project_id: str, db: Session = Depends(get_db)):
    """HTML web preview (§2.2): built fresh on request — string assembly only,
    no Chromium — with images served through the API."""
    from ..build.builder import build_web_preview

    p = _get_project(db, project_id)
    return FileResponse(build_web_preview(p), media_type="text/html")


@router.get("/projects/{project_id}/book/{tier}")
def book_pdf(project_id: str, tier: str, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    pdf = project_dirs(p.id)["rendered"] / f"book_{tier}.pdf"
    if not pdf.exists():
        raise HTTPException(404, f"No {tier} render yet")
    return FileResponse(pdf, media_type="application/pdf",
                        filename=f"{p.trip_name}-{tier}.pdf")


# ---------- jobs ----------

@router.get("/jobs/{job_id}")
def job_status(job_id: str, db: Session = Depends(get_db)):
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404)
    return {"id": j.id, "kind": j.kind, "status": j.status.value, "progress": j.progress,
            "note": j.progress_note, "result": j.result, "error": j.error}


@router.get("/projects/{project_id}/jobs")
def project_jobs(project_id: str, db: Session = Depends(get_db)):
    rows = (db.query(Job).filter_by(project_id=project_id)
            .order_by(Job.created_at.desc()).limit(20).all())
    return [{"id": j.id, "kind": j.kind, "status": j.status.value,
             "progress": j.progress, "note": j.progress_note} for j in rows]


# ---------- chat ----------

class ChatIn(BaseModel):
    message: str


@router.post("/projects/{project_id}/chat")
def chat(project_id: str, body: ChatIn, db: Session = Depends(get_db)):
    p = _get_project(db, project_id)
    return handle_message(db, p, body.message)


@router.get("/projects/{project_id}/changes")
def changes(project_id: str, db: Session = Depends(get_db)):
    rows = (db.query(ChangeLog).filter_by(project_id=project_id)
            .order_by(ChangeLog.created_at.desc()).limit(50).all())
    return [{"tool": r.tool, "args": r.args, "source": r.source,
             "at": r.created_at.isoformat()} for r in rows]


# ---------- templates ----------

@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    registry = json.loads((settings.templates_root / "registry.json").read_text())
    builtins = {t["id"]: t for t in registry["templates"]}
    out = [{**t, "builtin": True} for t in registry["templates"]]
    for t in db.query(Template).filter_by(builtin=False).all():
        out.append({"id": t.id, "name": t.name, "description": t.description,
                    "builtin": False, "base": t.base_template_id, "tokens": t.tokens,
                    "page_config": t.page_config or builtins.get(t.base_template_id, {}).get("page_config")})
    return out


class TemplateIn(BaseModel):
    id: str
    name: str
    description: str | None = None
    base_template_id: str
    tokens: dict = {}
    page_config: dict = {}


@router.post("/templates")
def save_template(body: TemplateIn, db: Session = Depends(get_db)):
    """Save a custom template (clone of a builtin + token overrides),
    reusable across all projects."""
    t = db.get(Template, body.id) or Template(id=body.id)
    t.name, t.description = body.name, body.description
    t.base_template_id, t.tokens, t.page_config = body.base_template_id, body.tokens, body.page_config
    t.builtin = False
    db.add(t)
    db.commit()
    return {"id": t.id}


# ---------- global settings ----------

KNOWN_PROVIDERS = ["anthropic", "google", "deepseek", "openai", "local"]


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    from ..ai.router import DEFAULT_ROUTES
    from ..models import AppSetting, TaskType as TT

    row = db.get(AppSetting, "ai_routes")
    saved = (row.value if row else None) or {}
    routes = {}
    for task, (prov, model) in DEFAULT_ROUTES.items():
        ov = saved.get(task.value) or {}
        routes[task.value] = {"provider": ov.get("provider", prov),
                              "model": ov.get("model", model),
                              "default_provider": prov, "default_model": model}
    return {"ai_routes": routes, "providers": KNOWN_PROVIDERS,
            "budget_alert_usd": settings.token_budget_alert_usd,
            "chunk_threshold_mb": settings.chunk_threshold_mb,
            "data_root": str(settings.data_root)}


class SettingsIn(BaseModel):
    ai_routes: dict[str, dict]


@router.post("/settings")
def save_settings(body: SettingsIn, db: Session = Depends(get_db)):
    from ..models import AppSetting

    row = db.get(AppSetting, "ai_routes") or AppSetting(key="ai_routes")
    row.value = body.ai_routes
    db.add(row)
    db.commit()
    return {"ok": True}


# ---------- cost dashboard ----------

@router.get("/costs")
def costs(db: Session = Depends(get_db)):
    def rollup(col):
        rows = (db.query(col, func.sum(AIRun.estimated_cost_usd),
                         func.sum(AIRun.input_tokens + AIRun.output_tokens),
                         func.count())
                .group_by(col).all())
        return [{"key": str(getattr(k, "value", k)), "cost_usd": round(c or 0, 4),
                 "tokens": int(t or 0), "calls": n} for k, c, t, n in rows]

    daily = (db.query(func.date(AIRun.created_at), func.sum(AIRun.estimated_cost_usd))
             .group_by(func.date(AIRun.created_at))
             .order_by(func.date(AIRun.created_at)).all())
    cache_saved = db.query(func.count()).filter(AIRun.cache_hit).scalar()
    return {
        "by_project": rollup(AIRun.project_id),
        "by_task": rollup(AIRun.task_type),
        "by_provider": rollup(AIRun.provider),
        "daily": [{"date": str(d), "cost_usd": round(c or 0, 4)} for d, c in daily],
        "cache_hits": cache_saved,
        "budget_alert_usd": settings.token_budget_alert_usd,
    }
