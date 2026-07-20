"""Classification service: classify once, cache forever (§5.2).

Cache key is the asset's content hash. A cache hit costs zero tokens and is
logged as such (cache_hit AIRun rows let the dashboard show money saved).
Manual overrides are never clobbered by a re-classification run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
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
    from ..ai.router import resolve_route

    route = resolve_route(TaskType.classification, project, db)
    _apply_result(db, project, asset, result, route.provider, route.model)
    db.commit()
    return result


def _apply_result(db: Session, project: Project, asset: Asset, result: dict,
                  provider: str, model: str) -> None:
    asset.classification = result
    role = result.get("suggested_role", "candid")
    asset.suggested_role = AssetRole(role) if role in AssetRole.__members__ else AssetRole.candid
    asset.classified_by_provider = provider
    asset.classified_by_model = model
    asset.classified_at = datetime.now(timezone.utc)


def _classify_batch_anthropic(db: Session, project: Project, assets: list[Asset],
                              progress) -> set[str]:
    """One Message Batches call for the whole backlog (§5.2: batch APIs cut
    cost). Returns the ids that succeeded; the caller retries the rest
    serially. Raises to trigger full serial fallback (no SDK, no key, ...)."""
    from ..ai.provider import AnthropicProvider, get_provider
    from ..ai.router import estimate_cost_usd, resolve_route

    route = resolve_route(TaskType.classification, project, db)
    provider = get_provider(route.provider)
    if not isinstance(provider, AnthropicProvider):
        raise RuntimeError("batch path is Anthropic-only for now")

    prompt = load_prompt("classification")
    images = [(a.id, Path(a.working_path or a.original_path)) for a in assets]
    progress(0.05, f"Submitted batch of {len(images)} photos")
    results = provider.classify_images_batch(system=prompt.system, images=images,
                                             model=route.model)
    ok: set[str] = set()
    by_id = {a.id: a for a in assets}
    for cid, resp in results.items():
        try:
            parsed = resp.json()
        except (ValueError, KeyError):
            continue
        _apply_result(db, project, by_id[cid], parsed, route.provider, route.model)
        db.add(AIRun(project_id=project.id, task_type=TaskType.classification,
                     provider=resp.provider, model=resp.model,
                     input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                     # Batch API bills at 50% of list price.
                     estimated_cost_usd=estimate_cost_usd(resp.model, resp.input_tokens,
                                                          resp.output_tokens) * 0.5,
                     agent="classification", prompt_version=prompt.version))
        ok.add(cid)
    db.commit()
    return ok


def classify_project(db: Session, project: Project, progress=lambda f, n: None) -> dict:
    """Walk every live asset. Cache hits and manual overrides are free; the
    unclassified backlog goes through the batch API when it's big enough,
    with serial as the fallback for stragglers and non-batch providers."""
    assets = [a for a in project.assets if a.duplicate_of is None]
    backlog = [a for a in assets if a.classification is None and not a.manual_override]
    cached = len(assets) - len(backlog)

    batched: set[str] = set()
    if len(backlog) >= settings.classification_batch_min:
        try:
            batched = _classify_batch_anthropic(db, project, backlog, progress)
        except Exception:  # noqa: BLE001 — batch is an optimization, never a blocker
            batched = set()

    done = 0
    for asset in assets:
        if asset.id not in batched:
            classify_asset(db, project, asset)
        done += 1
        progress(done / max(len(assets), 1), f"Classified {done}/{len(assets)}")
    return {"classified": len(backlog), "batched": len(batched),
            "cache_hits": cached, "total": len(assets)}
