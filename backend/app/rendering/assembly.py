"""Assembly primitives — the two OOM-proof techniques from the reference project.

1. HTML monolith assembly by string slicing, never DOM parsing. Parsing every
   chapter fragment with BeautifulSoup simultaneously OOMs past ~250-300MB of
   combined fragments; slicing between body markers is O(size) and flat-memory.

2. PDF assembly by qpdf/pikepdf streaming, never pypdf PdfWriter. pypdf builds
   the whole document's object graph in memory — a proven OOM path at
   90+ pages / hundreds of MB.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

import pikepdf

BODY_OPEN = "<!-- PBG:BODY -->"
BODY_CLOSE = "<!-- PBG:/BODY -->"


def chapter_fragment(chapter_id: str, inner_html: str) -> str:
    """Wrap chapter HTML in slice markers so it can be found and replaced in the
    monolith without parsing. The markers are HTML comments — invisible to
    rendering and immune to style-normalization passes."""
    return (
        f"<!-- PBG:CHAPTER {chapter_id} -->\n{inner_html}\n<!-- PBG:/CHAPTER {chapter_id} -->"
    )


def extract_body(fragment_html: str) -> str:
    """Slice the body content out of a standalone chapter file by marker,
    falling back to the whole string if unmarked."""
    start = fragment_html.find(BODY_OPEN)
    end = fragment_html.find(BODY_CLOSE)
    if start == -1 or end == -1:
        return fragment_html
    return fragment_html[start + len(BODY_OPEN):end]


def assemble_monolith(
    shell_before: str,
    shell_after: str,
    fragment_paths: Iterable[Path],
    out_path: Path,
) -> Path:
    """Stream chapter fragments between a document shell's head and tail.
    No fragment is ever parsed; each is read, sliced by marker, and appended.
    Memory use is bounded by the single largest fragment, not the book."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        out.write(shell_before)
        for frag_path in fragment_paths:
            out.write(extract_body(frag_path.read_text(encoding="utf-8")))
            out.write("\n")
        out.write(shell_after)
    return out_path


def replace_chapter_in_monolith(monolith_path: Path, chapter_id: str, new_inner_html: str) -> None:
    """Swap one chapter's slice in the assembled monolith by marker search —
    string find + concatenation, no DOM. Used by the edit-one-chapter flow."""
    open_marker = f"<!-- PBG:CHAPTER {chapter_id} -->"
    close_marker = f"<!-- PBG:/CHAPTER {chapter_id} -->"
    text = monolith_path.read_text(encoding="utf-8")
    start = text.find(open_marker)
    end = text.find(close_marker)
    if start == -1 or end == -1:
        raise ValueError(f"Chapter {chapter_id} markers not found in {monolith_path}")
    end += len(close_marker)
    monolith_path.write_text(
        text[:start] + chapter_fragment(chapter_id, new_inner_html) + text[end:],
        encoding="utf-8",
    )


def _qpdf_available() -> bool:
    return shutil.which("qpdf") is not None


def extract_page_range(src_pdf: Path, out_pdf: Path, first: int, last: int) -> Path:
    """Extract pages [first..last] (1-indexed, inclusive). qpdf when available
    (fastest, streaming); pikepdf otherwise (also streaming — pages are copied
    lazily, never the whole object graph)."""
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if _qpdf_available():
        subprocess.run(
            ["qpdf", str(src_pdf), "--pages", str(src_pdf), f"{first}-{last}", "--", str(out_pdf)],
            check=True, capture_output=True,
        )
        return out_pdf
    with pikepdf.open(src_pdf) as src, pikepdf.new() as dst:
        for i in range(first - 1, last):
            dst.pages.append(src.pages[i])
        dst.save(out_pdf)
    return out_pdf


def concat_pdfs(parts: list[Path], out_pdf: Path) -> Path:
    """Streaming concatenation of chapter/chunk PDFs into the book. Never pypdf."""
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if _qpdf_available():
        cmd = ["qpdf", "--empty", "--pages"]
        for p in parts:
            cmd += [str(p), "1-z"]
        cmd += ["--", str(out_pdf)]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_pdf
    with pikepdf.new() as dst:
        for p in parts:
            with pikepdf.open(p) as src:
                dst.pages.extend(src.pages)
        dst.save(out_pdf)
    return out_pdf


def page_count(pdf_path: Path) -> int:
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)
