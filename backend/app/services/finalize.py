"""Finalize Images (§5.3): one queued job that swaps every working derivative
for its full-resolution original across the whole project. No per-image
touching; progress reported on the Job row.

The swap is a flag flip — the builder resolves `finalized` assets to their
original path on the next build — so it's instant per asset and trivially
reversible (definalize on demand).
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Project


def finalize_images(db: Session, project: Project, progress=lambda f, n: None) -> dict:
    assets = [a for a in project.assets if a.duplicate_of is None]
    swapped = missing = 0
    for i, asset in enumerate(assets):
        if Path(asset.original_path).exists():
            asset.finalized = True
            swapped += 1
        else:
            missing += 1
        if i % 20 == 0:
            db.commit()
            progress((i + 1) / max(len(assets), 1), f"Finalized {i + 1}/{len(assets)}")
    for ch in project.chapters:
        ch.mark_dirty()  # every chapter re-renders with high-res on next Final
    db.commit()
    progress(1.0, f"Finalized {swapped} images" + (f", {missing} originals missing" if missing else ""))
    return {"finalized": swapped, "missing_originals": missing}
