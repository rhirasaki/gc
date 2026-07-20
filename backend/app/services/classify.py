"""Classification service: classify once, cache forever (§5.2).

Cache key is the asset's content hash. A cache hit costs zero tokens and is
logged as such (cache_hit AIRun rows let the dashboard show money saved).
Manual overrides are never clobbered by a re-classification run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Asset, AssetRole, AIRun, Project, TaskType
from ..agents.runner import load_prompt, run_image_agent


def classify_asset(db: Session, project: Project, asset: Asset, *, force: bool = False) -> dict | None:
    if asset.manual_override and not force:
        return asset.classification  # human decision wins, always
    if asset.classification and not force:
        # Same content already classified -> free.
        db.add(AIRun(project_id=project.id, task_type=TaskType.classification,
                     provider=asset.classified_by_provider or "cache",
                     model=asset.classified_by_model or "cache",
                     input_tokens=0, output_tokens=0, estimated_cost_usd=0.0,
                     cache_hit=True, agent="classification",
                     prompt_version=load_prompt("classification").version))
        db.commit()
        return asset.classification

    image = Path(asset.working_path or asset.original_path)
    result = run_image_agent(db, "classification", image, project=project)
    asset.classification = result
    role = result.get("suggested_role", "candid")
    asset.suggested_role = AssetRole(role) if role in AssetRole.__members__ else AssetRole.candid
    from ..ai.router import resolve_route

    route = resolve_route(TaskType.classification, project, db)
    asset.classified_by_provider = route.provider
    asset.classified_by_model = route.model
    asset.classified_at = datetime.now(timezone.utc)
    db.commit()
    return result


def classify_project(db: Session, project: Project, progress=lambda f, n: None) -> dict:
    """Batch walk. Skips manual overrides and cache hits; only unclassified
    content spends tokens."""
    assets = [a for a in project.assets if a.duplicate_of is None]
    done = spent = cached = 0
    for i, asset in enumerate(assets):
        had = asset.classification is not None
        classify_asset(db, project, asset)
        done += 1
        cached += 1 if had else 0
        spent += 0 if had else 1
        progress(done / max(len(assets), 1), f"Classified {done}/{len(assets)}")
    return {"classified": spent, "cache_hits": cached, "total": done}
