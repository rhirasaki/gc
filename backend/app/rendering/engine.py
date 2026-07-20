"""RenderEngine — HTML book -> print-ready PDF.

Binding architecture (§2.3 of the spec, carried from the reference project):

- Page-ranged export over fragment isolation: a chapter is NEVER rendered as a
  standalone document (isolated fragments paginate differently than the same
  content inside the full flow). The full monolith is loaded once per
  Chromium invocation and only the requested page range is exported.
- Chunked one-process-per-chunk rendering engages automatically once the
  payload exceeds settings.chunk_threshold_mb: each chunk is a fresh
  subprocess that loads the full document and exports its page range, and the
  chunks are concatenated by streaming qpdf/pikepdf (assembly.concat_pdfs).
- Swap/disk preflight runs before every heavy render session.

The book layout system emits explicit fixed-size `.page` elements (one element
per PDF page), which makes the PAGE_MAP exact and computable from the HTML by
string scanning — no render needed to know which pages a chapter occupies.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ..config import settings
from . import assembly
from .preflight import run_preflight

_IMG_SRC_RE = re.compile(r'src="file://([^"]+)"')
# Matches only page elements (class list beginning with "page"), never
# descendants like "page-inner".
_PAGE_DIV_RE = re.compile(r'class="page[ "]')
_CHAPTER_OPEN_RE = re.compile(r"<!-- PBG:CHAPTER (\w+) -->")


@dataclass
class PageMapEntry:
    chapter_id: str
    page_start: int  # 1-indexed inclusive
    page_end: int


@dataclass
class RenderResult:
    pdf_path: Path
    total_pages: int
    page_map: list[PageMapEntry]
    chunked: bool
    payload_mb: float
    warnings: list[str] = field(default_factory=list)


class RenderEngine(Protocol):
    def render_book(self, monolith_html: Path, out_pdf: Path) -> RenderResult: ...
    def render_chapter_range(
        self, monolith_html: Path, out_pdf: Path, first: int, last: int
    ) -> Path: ...


def measure_payload_mb(monolith_html: Path) -> float:
    """HTML size plus every locally referenced image, in MB. This is the number
    the chunking decision keys off — measured, not guessed."""
    total = monolith_html.stat().st_size
    html = monolith_html.read_text(encoding="utf-8")
    seen: set[str] = set()
    for m in _IMG_SRC_RE.finditer(html):
        p = m.group(1)
        if p in seen:
            continue
        seen.add(p)
        f = Path(p)
        if f.exists():
            total += f.stat().st_size
    return total / 1024**2


def compute_page_map(monolith_html: Path) -> list[PageMapEntry]:
    """Exact chapter->page mapping by counting `.page` elements per chapter
    slice. Pure string scanning (never DOM parsing — reference §4.2)."""
    html = monolith_html.read_text(encoding="utf-8")
    entries: list[PageMapEntry] = []
    # Pages before the first chapter (cover/front matter) shift everything.
    first_chapter = _CHAPTER_OPEN_RE.search(html)
    preamble_pages = len(_PAGE_DIV_RE.findall(html[: first_chapter.start()])) if first_chapter else 0
    cursor = preamble_pages
    for m in _CHAPTER_OPEN_RE.finditer(html):
        cid = m.group(1)
        close = html.find(f"<!-- PBG:/CHAPTER {cid} -->", m.end())
        slice_pages = len(_PAGE_DIV_RE.findall(html[m.end(): close]))
        entries.append(PageMapEntry(cid, cursor + 1, cursor + slice_pages))
        cursor += slice_pages
    return entries


class PlaywrightRenderEngine:
    """Chromium print-to-PDF via Playwright, with the chunked subprocess
    fallback. All Chromium work for chunked renders happens in fresh worker
    processes (chunk_worker.py) so render-cost non-linearity and leaked memory
    never accumulate in the app process."""

    def __init__(
        self,
        chunk_threshold_mb: float | None = None,
        chunk_pages: int | None = None,
    ) -> None:
        self.chunk_threshold_mb = chunk_threshold_mb or settings.chunk_threshold_mb
        self.chunk_pages = chunk_pages or settings.chunk_pages

    # -- single-invocation render (also used per-chunk inside workers) -------

    @staticmethod
    def _print_pdf(monolith_html: Path, out_pdf: Path, page_range: str | None) -> None:
        from playwright.sync_api import sync_playwright

        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            launch_kwargs: dict = {"args": ["--disable-dev-shm-usage"]}
            if settings.chromium_executable:
                launch_kwargs["executable_path"] = settings.chromium_executable
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page()
                page.goto(monolith_html.resolve().as_uri(), wait_until="networkidle",
                          timeout=settings.render_timeout_s * 1000)
                kwargs: dict = {
                    "path": str(out_pdf),
                    "print_background": True,
                    "prefer_css_page_size": True,
                }
                if page_range:
                    kwargs["page_ranges"] = page_range
                page.pdf(**kwargs)
            finally:
                browser.close()

    # -- public API ----------------------------------------------------------

    def render_chapter_range(self, monolith_html: Path, out_pdf: Path, first: int, last: int) -> Path:
        """Export one page range from the FULL document flow (never an isolated
        fragment). Used by the edit-one-chapter loop."""
        self._print_pdf(monolith_html, out_pdf, f"{first}-{last}")
        return out_pdf

    def render_book(self, monolith_html: Path, out_pdf: Path) -> RenderResult:
        payload_mb = measure_payload_mb(monolith_html)
        heavy = payload_mb >= settings.heavy_render_payload_mb
        report = run_preflight(out_pdf.parent, heavy=heavy)
        page_map = compute_page_map(monolith_html)
        total_pages = page_map[-1].page_end if page_map else 0
        # front/back matter outside chapters:
        html = monolith_html.read_text(encoding="utf-8")
        all_pages = len(_PAGE_DIV_RE.findall(html))
        total_pages = max(total_pages, all_pages)

        if payload_mb < self.chunk_threshold_mb:
            self._print_pdf(monolith_html, out_pdf, None)
            return RenderResult(out_pdf, assembly.page_count(out_pdf), page_map,
                                chunked=False, payload_mb=payload_mb, warnings=report.messages)

        # Chunked fallback: fixed-size page chunks, one fresh process each.
        chunk_dir = out_pdf.parent / f".chunks-{out_pdf.stem}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        parts: list[Path] = []
        for start in range(1, all_pages + 1, self.chunk_pages):
            end = min(start + self.chunk_pages - 1, all_pages)
            part = chunk_dir / f"chunk-{start:04d}-{end:04d}.pdf"
            self._render_chunk_subprocess(monolith_html, part, start, end)
            parts.append(part)
        assembly.concat_pdfs(parts, out_pdf)
        for p in parts:
            p.unlink(missing_ok=True)
        chunk_dir.rmdir()
        return RenderResult(out_pdf, assembly.page_count(out_pdf), page_map,
                            chunked=True, payload_mb=payload_mb, warnings=report.messages)

    @staticmethod
    def _render_chunk_subprocess(monolith_html: Path, out_pdf: Path, first: int, last: int) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "app.rendering.chunk_worker",
             str(monolith_html), str(out_pdf), str(first), str(last)],
            cwd=Path(__file__).resolve().parent.parent.parent,
            capture_output=True, text=True, timeout=settings.render_timeout_s,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Chunk render {first}-{last} failed (exit {proc.returncode}): {proc.stderr[-2000:]}"
            )


def get_engine() -> PlaywrightRenderEngine:
    return PlaywrightRenderEngine()
