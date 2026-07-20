"""Background jobs. Default backend is a local thread pool (zero external
dependencies — the lightest thing a solo operator can run); RQ/Redis is a
config switch (settings.job_backend="rq") without changing callers. State of
record is always the Job row, so the UI polls the DB regardless of backend.

Render jobs run the heavy Chromium work in subprocesses (chunk workers), so
these threads only wait on I/O — the GIL is not a bottleneck here.
"""
from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Chapter, Job, JobStatus, Project

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pbg-job")


def _set(db: Session, job: Job, **kw) -> None:
    for k, v in kw.items():
        setattr(job, k, v)
    db.commit()


def _dispatch(db: Session, project: Project | None, job: Job, progress) -> dict:
    from ..build.builder import build_monolith
    from ..rendering.book import cleanup_artifacts, render_final, stitch_preview
    from ..services.classify import classify_project
    from ..services.finalize import finalize_images
    from ..services.narrative import generate_chapter_narrative

    params = job.params or {}
    if job.kind == "render_final":
        r = render_final(db, project, build_monolith(project), progress)
        return {"pdf": str(r.pdf_path), "pages": r.total_pages, "chunked": r.chunked,
                "payload_mb": round(r.payload_mb, 1)}
    if job.kind == "render_preview":
        pdf = stitch_preview(db, project, build_monolith(project), progress)
        return {"pdf": str(pdf)}
    if job.kind == "finalize_images":
        return finalize_images(db, project, progress)
    if job.kind == "classify_batch":
        return classify_project(db, project, progress)
    if job.kind == "cleanup_artifacts":
        return cleanup_artifacts(project.id)
    if job.kind == "regenerate_narrative":
        chapter = db.get(Chapter, params["chapter_id"])
        out = generate_chapter_narrative(db, project, chapter,
                                         tone=params.get("tone"),
                                         word_count=int(params.get("word_count", 350)))
        return {"chapter": chapter.label,
                "ungrounded": out["grounding"].get("ungrounded_count", 0)}
    raise ValueError(f"Unknown job kind: {job.kind}")


def _run_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        _set(db, job, status=JobStatus.running, started_at=datetime.now(timezone.utc))

        def progress(frac: float, note: str) -> None:
            _set(db, job, progress=round(frac, 3), progress_note=note)

        project = db.get(Project, job.project_id) if job.project_id else None
        result = _dispatch(db, project, job, progress)
        _set(db, job, status=JobStatus.done, progress=1.0, result=result,
             finished_at=datetime.now(timezone.utc))
    except Exception as exc:  # noqa: BLE001 — job boundary must not kill the worker
        db.rollback()
        job = db.get(Job, job_id)
        _set(db, job, status=JobStatus.failed,
             error=f"{exc}\n{traceback.format_exc()[-2000:]}",
             finished_at=datetime.now(timezone.utc))
    finally:
        db.close()


def enqueue(db: Session, project_id: str | None, kind: str, params: dict | None = None) -> Job:
    job = Job(project_id=project_id, kind=kind, params=params or {})
    db.add(job)
    db.commit()
    _executor.submit(_run_job, job.id)
    return job
