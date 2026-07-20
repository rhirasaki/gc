"""Layout selection (§8): a constrained system of variants, deterministically
chosen from photo count, aspect mix, and narrative length. "Unique, not
cookie-cutter" comes from the variant system, never from randomness — the
same inputs always produce the same book.

The pinned-hero escape hatch: chapter.pinned_hero_asset_id wins outright and
is removed from auto-selection for grids.
"""
from __future__ import annotations

from dataclasses import dataclass

# Page component variants every template styles with its own tokens.
GRID_VARIANTS = {
    "feature-clean",   # one full-bleed hero page
    "duo-vertical",    # two portrait photos side by side
    "trio-band",       # three across a band under text
    "quad-grid",       # 2x2
    "text-feature",    # narrative page with one supporting image
    "pull-quote",      # quote page, no photos
    "pano-spread",     # one panoramic across the page
}


@dataclass
class PagePlan:
    component: str
    asset_ids: list[str]


def _hero_score(asset) -> float:
    cls = asset.classification or {}
    quality = float(cls.get("quality_score", 0.5))
    role_bonus = 0.25 if cls.get("suggested_role") == "hero" else 0.0
    aspect_bonus = 0.1 if asset.aspect_class in ("3:2", "16:9", "4:3") else 0.0
    blur_penalty = 0.15 if (asset.blur_score or 1000) < 200 else 0.0
    # Local rule-of-thirds signal (0..1), weighted lightly under the AI score.
    thirds_bonus = 0.15 * (getattr(asset, "composition_score", None) or 0.0)
    return quality + role_bonus + aspect_bonus + thirds_bonus - blur_penalty


def pick_hero(chapter) -> str | None:
    if chapter.pinned_hero_asset_id:
        return chapter.pinned_hero_asset_id
    assets = [ca.asset for ca in chapter.chapter_assets]
    if not assets:
        return None
    return max(assets, key=_hero_score).id


def plan_chapter_layout(chapter, narrative_words: int) -> list[PagePlan]:
    """Deterministic page plan for one chapter. The mix of variants shifts
    with photo count / aspect classes / narrative length so consecutive
    chapters don't repeat the same rhythm, but the vocabulary is fixed."""
    hero = pick_hero(chapter)
    ordered = [ca.asset for ca in chapter.chapter_assets]
    rest = [a for a in ordered if a.id != hero]
    plans: list[PagePlan] = []

    if hero:
        plans.append(PagePlan("feature-clean", [hero]))

    text_pages = max(1, narrative_words // 320)
    text_support = rest[:text_pages]
    for a in text_support:
        plans.append(PagePlan("text-feature", [a.id]))
    remaining = rest[text_pages:]

    panos = [a for a in remaining if a.aspect_class == "pano"]
    for p in panos:
        plans.append(PagePlan("pano-spread", [p.id]))
    remaining = [a for a in remaining if a.aspect_class != "pano"]

    portraits = [a for a in remaining if a.aspect_class and a.aspect_class.startswith("portrait")]
    while len(portraits) >= 2:
        pair, portraits = portraits[:2], portraits[2:]
        plans.append(PagePlan("duo-vertical", [a.id for a in pair]))
        remaining = [a for a in remaining if a not in pair]
    remaining = [a for a in remaining if a not in portraits] + portraits

    while remaining:
        if len(remaining) >= 4:
            batch, remaining = remaining[:4], remaining[4:]
            plans.append(PagePlan("quad-grid", [a.id for a in batch]))
        elif len(remaining) == 3:
            plans.append(PagePlan("trio-band", [a.id for a in remaining]))
            remaining = []
        else:
            for a in remaining:
                plans.append(PagePlan("text-feature", [a.id]))
            remaining = []

    # Long, well-noted chapters earn a breather pull-quote page.
    if narrative_words > 500:
        plans.insert(min(2, len(plans)), PagePlan("pull-quote", []))
    return plans
