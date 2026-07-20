"""Book-level render orchestration: the two render tiers.

- FINAL: full-document render of the monolith (direct or chunked, engine
  decides from measured payload). Afterwards each chapter's page range is
  extracted into a per-chapter cache PDF (streaming qpdf), page ranges are
  written back, and dirty flags clear.

- PREVIEW: cheap stitch. Unchanged chapters come from the per-chapter cache;
  dirty chapters are re-exported from the CURRENT monolith by page range
  (full-document load, page-ranged export — never fragment isolation), then
  everything is concatenated streaming. Cost scales with what changed, not
  with book size.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Chapter, Project
from . import assembly
from .engine import RenderResult, get_engine


def project_dirs(project_id: str) -> dict[str, Path]:
    root = settings.data_root / project_id
    dirs = {
        "root": root,
        "originals": root / "originals",
        "working": root / "working",
        "chapters": root / "chapters",
        "rendered": root / "rendered",
        "cache": root / "rendered" / "chapter_cache",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def render_final(db: Session, project: Project, monolith_html: Path,
                 progress=lambda frac, note: None) -> RenderResult:
    dirs = project_dirs(project.id)
    out_pdf = dirs["rendered"] / "book_final.pdf"
    engine = get_engine()
    progress(0.05, "Rendering full book")
    result = engine.render_book(monolith_html, out_pdf)

    progress(0.7, "Caching chapter page ranges")
    by_id = {c.id: c for c in project.chapters}
    for i, entry in enumerate(result.page_map):
        ch = by_id.get(entry.chapter_id)
        if ch is None:
            continue
        ch.page_start, ch.page_end = entry.page_start, entry.page_end
        cache_pdf = dirs["cache"] / f"{ch.id}.pdf"
        assembly.extract_page_range(out_pdf, cache_pdf, entry.page_start, entry.page_end)
        ch.rendered_pdf_path = str(cache_pdf)
        ch.rendered_at = datetime.now(timezone.utc)
        ch.changed_since_final = False
        progress(0.7 + 0.3 * (i + 1) / max(len(result.page_map), 1), f"Cached {ch.label}")
    db.commit()
    return result


def stitch_preview(db: Session, project: Project, monolith_html: Path,
                   progress=lambda frac, note: None) -> Path:
    """Preview = cached chapter PDFs + fresh page-ranged exports for dirty
    chapters only. Falls back to a full render when nothing is cached yet."""
    dirs = project_dirs(project.id)
    out_pdf = dirs["rendered"] / "book_preview.pdf"
    engine = get_engine()
    chapters = sorted(project.chapters, key=lambda c: c.position)

    never_finalized = any(c.page_start is None for c in chapters)
    if never_finalized:
        progress(0.1, "No cached render yet — full preview render")
        engine.render_book(monolith_html, out_pdf)
        return out_pdf

    from .engine import compute_page_map
    current_map = {e.chapter_id: e for e in compute_page_map(monolith_html)}
    parts: list[Path] = []
    for i, ch in enumerate(chapters):
        cached = Path(ch.rendered_pdf_path) if ch.rendered_pdf_path else None
        if not ch.changed_since_final and cached and cached.exists():
            parts.append(cached)
        else:
            entry = current_map.get(ch.id)
            if entry is None:
                continue
            fresh = dirs["cache"] / f"{ch.id}.preview.pdf"
            progress(0.1 + 0.8 * i / max(len(chapters), 1), f"Re-rendering {ch.label}")
            engine.render_chapter_range(monolith_html, fresh, entry.page_start, entry.page_end)
            parts.append(fresh)
    progress(0.95, "Stitching preview")
    assembly.concat_pdfs(parts, out_pdf)
    return out_pdf


def cleanup_artifacts(project_id: str) -> dict:
    """Remove redundant intermediates: preview-chapter PDFs, orphaned chunk
    dirs, stale preview books. User-triggerable and schedulable (§12)."""
    dirs = project_dirs(project_id)
    removed, freed = 0, 0
    for pattern in ("chapter_cache/*.preview.pdf", ".chunks-*/*", ".chunks-*"):
        for p in sorted(dirs["rendered"].glob(pattern), reverse=True):
            if p.is_file():
                freed += p.stat().st_size
                p.unlink()
                removed += 1
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()
    return {"removed": removed, "freed_mb": round(freed / 1024**2, 1)}
