"""Note ingestion (§2.1): many source formats -> one normalized Note shape.

Each parser returns list[NormalizedNote]; nothing downstream ever sees a
source-specific structure.
"""
from __future__ import annotations

import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..models import NoteSource


@dataclass
class NormalizedNote:
    text: str
    source_type: NoteSource
    title: str | None = None
    noted_at: datetime | None = None
    raw_metadata: dict | None = None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def _strip_html(html: str) -> str:
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("</div>", "\n").replace("</p>", "\n")
    text = _TAG_RE.sub("", text)
    return _WS_RE.sub("\n\n", text).strip()


def parse_pasted(text: str, title: str | None = None) -> list[NormalizedNote]:
    return [NormalizedNote(text=text.strip(), source_type=NoteSource.pasted, title=title)]


def parse_txt(path: Path) -> list[NormalizedNote]:
    return [NormalizedNote(text=path.read_text(encoding="utf-8", errors="replace").strip(),
                           source_type=NoteSource.txt, title=path.stem)]


def parse_apple_notes_html(path: Path) -> list[NormalizedNote]:
    """Apple Notes exports arrive as one HTML file per note."""
    html = path.read_text(encoding="utf-8", errors="replace")
    title_m = re.search(r"<title>(.*?)</title>", html, re.S)
    return [NormalizedNote(
        text=_strip_html(html), source_type=NoteSource.apple_notes,
        title=title_m.group(1).strip() if title_m else path.stem,
    )]


def parse_google_keep_json(path: Path) -> list[NormalizedNote]:
    """Google Takeout Keep export: one JSON per note."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ts = data.get("userEditedTimestampUsec")
    noted_at = (datetime.fromtimestamp(ts / 1_000_000, tz=timezone.utc) if ts else None)
    text = data.get("textContent") or ""
    if not text and data.get("listContent"):
        text = "\n".join(f"- {i.get('text', '')}" for i in data["listContent"])
    return [NormalizedNote(text=text.strip(), source_type=NoteSource.google_keep,
                           title=data.get("title") or path.stem, noted_at=noted_at,
                           raw_metadata={"labels": data.get("labels", [])})]


def parse_docx(path: Path) -> list[NormalizedNote]:
    """Word document: pull paragraph text straight from document.xml — no
    python-docx dependency needed for plain narrative notes."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    paras = re.split(r"</w:p>", xml)
    lines = []
    for p in paras:
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)
        if runs:
            lines.append("".join(runs))
    return [NormalizedNote(text="\n".join(lines).strip(), source_type=NoteSource.word,
                           title=path.stem)]


def parse_any(path: Path) -> list[NormalizedNote]:
    ext = path.suffix.lower()
    if ext in (".txt", ".md"):
        return parse_txt(path)
    if ext in (".html", ".htm"):
        return parse_apple_notes_html(path)
    if ext == ".json":
        return parse_google_keep_json(path)
    if ext == ".docx":
        return parse_docx(path)
    raise ValueError(f"Unsupported note format: {ext}")
