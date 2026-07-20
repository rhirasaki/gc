"""Book HTML builder: project -> chapter fragments -> marked monolith.

- Every page is an explicit fixed-size .page element (exact PAGE_MAP).
- All styling is classes + template tokens; the only per-element attributes
  are image srcs and text content (§2.3: CSS classes over inline styles).
- Draft builds reference working derivatives; after Finalize Images, the same
  builder emits original paths — nothing else changes.
- Chapter HTML is wrapped in PBG:CHAPTER markers so single-chapter edits are
  string-sliced into the monolith without reparsing (assembly module).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..config import settings
from ..layout.selector import PagePlan, pick_hero, plan_chapter_layout
from ..models import Chapter, Project
from ..rendering import assembly
from ..rendering.book import project_dirs


def _esc(s: str | None) -> str:
    return html.escape(s or "")


def _img_uri(asset) -> str:
    path = Path(asset.original_path if asset.finalized else (asset.working_path or asset.original_path))
    return path.resolve().as_uri().replace("file://", "file://")


def _tokens_css(project: Project) -> str:
    template_id = project.template_id or settings.default_template
    css_path = settings.templates_root / template_id / "tokens.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    # Custom templates: DB tokens override the base bundle's custom properties.
    if project.template and project.template.tokens:
        overrides = "\n".join(f"  {k}: {v};" for k, v in project.template.tokens.items())
        css += f"\n:root {{\n{overrides}\n}}\n"
    # Coastal/Tropical keys accents to the trip's sampled palette.
    if project.sampled_palette and template_id == "coastal-tropical":
        pal = project.sampled_palette
        css += f"\n:root {{ --accent: {pal[0]}; --accent-2: {pal[1] if len(pal) > 1 else pal[0]}; }}\n"
    return css


def shell(project: Project) -> tuple[str, str]:
    base_css = (settings.templates_root / "base" / "layout.css").read_text(encoding="utf-8")
    head = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(project.trip_name)}</title>"
        f"<style>{base_css}</style><style>{_tokens_css(project)}</style>"
        f"</head><body>\n{assembly.BODY_OPEN}\n"
    )
    tail = f"\n{assembly.BODY_CLOSE}\n</body></html>"
    return head, tail


def cover_page(project: Project, hero_uri: str | None) -> str:
    dates = ""
    if project.date_start and project.date_end:
        dates = f"{project.date_start.strftime('%B %Y')}"
    photo = f'<img class="cover-photo" src="{hero_uri}">' if hero_uri else ""
    return (
        f'<div class="page cover">{photo}<div class="cover-scrim"></div>'
        f'<div class="cover-text"><div class="cover-title">{_esc(project.trip_name)}</div>'
        f'<div class="cover-subtitle">{_esc(" · ".join(project.destinations or []))}'
        f'{" · " + dates if dates else ""}</div></div></div>'
    )


def front_matter_page(project: Project) -> str:
    n_photos = len([a for a in project.assets if a.duplicate_of is None])
    n_days = len(project.chapters)
    n_places = len(project.map_pins)
    syn = f'<p class="narrative">{_esc(project.synopsis)}</p>' if project.synopsis else ""
    return (
        '<div class="page stats-page"><div class="page-inner">'
        f'<div class="stats-title">{_esc(project.trip_name)}</div>'
        '<div class="stats-strip">'
        f'<div class="stat"><div class="stat-value">{n_days}</div><div class="stat-label">Chapters</div></div>'
        f'<div class="stat"><div class="stat-value">{n_photos}</div><div class="stat-label">Photographs</div></div>'
        f'<div class="stat"><div class="stat-value">{n_places}</div><div class="stat-label">Places</div></div>'
        f'</div>{syn}</div></div>'
    )


def _figure(asset, caption: str | None) -> str:
    cap = f"<figcaption>{_esc(caption)}</figcaption>" if caption else ""
    return f'<figure><img src="{_img_uri(asset)}">{cap}</figure>'


def _page(inner: str, classes: str, folio: int | None) -> str:
    f = f'<div class="folio">{folio}</div>' if folio else ""
    return f'<div class="page {classes}">{inner}{f}</div>'


def chapter_html(project: Project, chapter: Chapter, folio_start: int) -> str:
    """Chapter fragment: divider page + planned pages, wrapped in markers."""
    assets_by_id = {ca.asset_id: ca.asset for ca in chapter.chapter_assets}
    captions = {ca.asset_id: ca.caption for ca in chapter.chapter_assets}
    words = len((chapter.narrative or "").split())
    plans: list[PagePlan] = (
        [PagePlan(**p) for p in chapter.layout_plan["pages"]]
        if chapter.layout_plan and "pages" in chapter.layout_plan
        else plan_chapter_layout(chapter, words)
    )

    hero_id = pick_hero(chapter)
    hero_uri = _img_uri(assets_by_id[hero_id]) if hero_id and hero_id in assets_by_id else None
    pages: list[str] = []
    kicker = f"Chapter {chapter.position + 1}"
    photo = f'<img class="divider-photo" src="{hero_uri}">' if hero_uri else ""
    pages.append(
        f'<div class="page divider">{photo}<div class="divider-scrim"></div>'
        f'<div class="divider-text"><div class="divider-kicker">{_esc(kicker)}</div>'
        f'<div class="divider-title">{_esc(chapter.label)}</div></div></div>'
    )

    paragraphs = [p for p in (chapter.narrative or "").split("\n\n") if p.strip()]
    narrative_used = False
    folio = folio_start + 1
    for plan in plans:
        pl_assets = [assets_by_id[a] for a in plan.asset_ids if a in assets_by_id]
        if plan.component == "feature-clean" and pl_assets:
            a = pl_assets[0]
            pages.append(_page(f'<figure class="fig-feature"><img src="{_img_uri(a)}">'
                               f'{f"<figcaption>{_esc(captions.get(a.id))}</figcaption>" if captions.get(a.id) else ""}</figure>',
                               "feature", None))
        elif plan.component == "text-feature":
            text = ""
            if not narrative_used and paragraphs:
                body = "".join(f"<p>{_esc(p)}</p>" for p in paragraphs)
                text = f'<div class="chapter-head">{_esc(chapter.label)}</div><div class="narrative">{body}</div>'
                narrative_used = True
            elif pl_assets:
                text = f'<div class="narrative"><p>{_esc(captions.get(pl_assets[0].id) or "")}</p></div>'
            img = _figure(pl_assets[0], None) if pl_assets else ""
            pages.append(_page(f'<div class="page-inner"><div class="tf-text">{text}</div>'
                               f'<div class="tf-photo">{img}</div></div>', "text-feature", folio))
        elif plan.component in ("duo-vertical", "trio-band", "quad-grid") and pl_assets:
            figs = "".join(_figure(a, captions.get(a.id)) for a in pl_assets)
            pages.append(_page(f'<div class="page-inner">{figs}</div>',
                               f"grid-page {plan.component}", folio))
        elif plan.component == "pano-spread" and pl_assets:
            pages.append(_page(f'<div class="page-inner">{_figure(pl_assets[0], captions.get(pl_assets[0].id))}</div>',
                               "pano-spread", folio))
        elif plan.component == "pull-quote":
            quote = ""
            if chapter.grounding_report is None and paragraphs:
                quote = paragraphs[0].split(".")[0]
            lp = chapter.layout_plan or {}
            quote = lp.get("pull_quote") or quote
            if quote:
                pages.append(_page(f'<div class="page-inner"><div class="pull-quote">{_esc(quote)}</div></div>',
                                   "pull-quote-page", folio))
        folio += 1

    # Narrative must always land somewhere even if no text-feature page ran.
    if not narrative_used and paragraphs:
        body = "".join(f"<p>{_esc(p)}</p>" for p in paragraphs)
        pages.insert(1, _page(
            f'<div class="page-inner"><div class="tf-text"><div class="chapter-head">{_esc(chapter.label)}</div>'
            f'<div class="narrative">{body}</div></div></div>', "text-feature", folio_start + 1))

    return assembly.chapter_fragment(chapter.id, "\n".join(pages))


def build_monolith(project: Project) -> Path:
    """Write chapter fragments + assemble the marked monolith by streaming."""
    dirs = project_dirs(project.id)
    head, tail = shell(project)

    chapters = sorted(project.chapters, key=lambda c: c.position)
    cover_hero = None
    for ch in chapters:
        hid = pick_hero(ch)
        if hid:
            a = next((ca.asset for ca in ch.chapter_assets if ca.asset_id == hid), None)
            if a:
                cover_hero = _img_uri(a)
                break

    preamble = cover_page(project, cover_hero) + front_matter_page(project)
    fragment_paths: list[Path] = []
    folio = 2  # cover + front matter
    for ch in chapters:
        frag_path = dirs["chapters"] / f"{ch.id}.html"
        frag_path.write_text(chapter_html(project, ch, folio), encoding="utf-8")
        fragment_paths.append(frag_path)
        folio += chapter_page_count(frag_path)

    monolith = dirs["root"] / "book.html"
    assembly.assemble_monolith(head + preamble, tail, fragment_paths, monolith)
    return monolith


def chapter_page_count(frag_path: Path) -> int:
    return frag_path.read_text(encoding="utf-8").count('class="page ')


def rebuild_chapter(project: Project, chapter: Chapter) -> Path:
    """Regenerate one chapter's fragment and splice it into the monolith by
    marker (string ops only). Page counts can shift; the page map is always
    recomputed from the monolith, so drift is impossible."""
    dirs = project_dirs(project.id)
    monolith = dirs["root"] / "book.html"
    folio = chapter.page_start - 1 if chapter.page_start else 0
    frag = chapter_html(project, chapter, folio)
    (dirs["chapters"] / f"{chapter.id}.html").write_text(frag, encoding="utf-8")
    if monolith.exists():
        # chapter_html() returns the marker-wrapped fragment; the splice API
        # takes the inner html and re-wraps, so unwrap between the markers.
        inner = frag.split("-->", 1)[1].rsplit("<!--", 1)[0].strip()
        assembly.replace_chapter_in_monolith(monolith, chapter.id, inner)
    else:
        build_monolith(project)
    return monolith
