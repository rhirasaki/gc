"""Tests for the binding rendering architecture (§2.3): string-slicing
assembly, page map math, streaming PDF ops, preflight checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pikepdf
import pytest

from app.rendering import assembly
from app.rendering.engine import compute_page_map, measure_payload_mb
from app.rendering.preflight import PreflightError, read_swap_mb, run_preflight


def _page(n: int) -> str:
    return f'<div class="page text-feature">page {n}</div>'


def make_monolith(tmp_path: Path) -> Path:
    frags = []
    for cid, pages in [("aaa", 3), ("bbb", 2), ("ccc", 4)]:
        inner = "\n".join(_page(i) for i in range(pages))
        f = tmp_path / f"{cid}.html"
        f.write_text(assembly.chapter_fragment(cid, inner))
        frags.append(f)
    head = f"<html><body>\n{assembly.BODY_OPEN}\n" + _page(0) + _page(0)  # cover + front matter
    tail = f"\n{assembly.BODY_CLOSE}\n</body></html>"
    return assembly.assemble_monolith(head, tail, frags, tmp_path / "book.html")


def test_assemble_and_page_map(tmp_path):
    monolith = make_monolith(tmp_path)
    pm = compute_page_map(monolith)
    assert [(e.chapter_id, e.page_start, e.page_end) for e in pm] == [
        ("aaa", 3, 5), ("bbb", 6, 7), ("ccc", 8, 11)]


def test_replace_chapter_string_slicing(tmp_path):
    monolith = make_monolith(tmp_path)
    assembly.replace_chapter_in_monolith(monolith, "bbb", _page(0))  # 2 pages -> 1
    pm = compute_page_map(monolith)
    assert [(e.chapter_id, e.page_start, e.page_end) for e in pm] == [
        ("aaa", 3, 5), ("bbb", 6, 6), ("ccc", 7, 10)]
    text = monolith.read_text()
    assert text.count("PBG:CHAPTER bbb") == 1


def test_replace_missing_chapter_raises(tmp_path):
    monolith = make_monolith(tmp_path)
    with pytest.raises(ValueError):
        assembly.replace_chapter_in_monolith(monolith, "zzz", "x")


def _mk_pdf(path: Path, pages: int):
    pdf = pikepdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(200, 200))
    pdf.save(path)


def test_concat_and_extract_streaming(tmp_path):
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    _mk_pdf(a, 3)
    _mk_pdf(b, 2)
    out = tmp_path / "out.pdf"
    assembly.concat_pdfs([a, b], out)
    assert assembly.page_count(out) == 5
    part = tmp_path / "part.pdf"
    assembly.extract_page_range(out, part, 2, 4)
    assert assembly.page_count(part) == 3


def test_measure_payload_counts_images(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"0" * 1024 * 1024)
    html = tmp_path / "m.html"
    html.write_text(f'<div class="page"><img src="file://{img}"><img src="file://{img}"></div>')
    mb = measure_payload_mb(html)
    assert 1.0 <= mb < 1.1  # image counted once despite two references


def test_preflight_disk_failure(tmp_path):
    with pytest.raises(PreflightError):
        run_preflight(tmp_path, heavy=True, min_free_gb=10**9, require_swap=False)


def test_preflight_swap_parse(tmp_path):
    f = tmp_path / "swaps"
    f.write_text("Filename Type Size Used Priority\n/swapfile file 2097148 0 -2\n")
    assert read_swap_mb(f) == pytest.approx(2097148 / 1024)
    f.write_text("Filename Type Size Used Priority\n")
    assert read_swap_mb(f) == 0.0


def test_preflight_light_render_warns_not_raises(tmp_path):
    r = run_preflight(tmp_path, heavy=False, min_free_gb=10**9, require_swap=True)
    assert not r.ok and r.messages
