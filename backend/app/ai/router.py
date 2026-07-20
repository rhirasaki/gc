"""Task-type -> (provider, model) routing with per-project overrides (§7),
plus cost estimation and AIRun logging. Every AI call in the app goes through
run_text()/run_image() so nothing escapes the cost ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import AIRun, Project, TaskType
from .provider import AIResponse, get_provider

# Default posture per §7's table. All swappable in Settings / per project.
DEFAULT_ROUTES: dict[TaskType, tuple[str, str]] = {
    TaskType.classification: ("anthropic", "claude-haiku-4-5-20251001"),
    TaskType.narrative: ("anthropic", "claude-sonnet-5"),
    TaskType.research: ("anthropic", "claude-sonnet-5"),
    TaskType.chat: ("anthropic", "claude-haiku-4-5-20251001"),
    TaskType.grounding: ("anthropic", "claude-haiku-4-5-20251001"),
    TaskType.synopsis: ("anthropic", "claude-haiku-4-5-20251001"),
    TaskType.layout: ("anthropic", "claude-haiku-4-5-20251001"),
    TaskType.ingestion: ("anthropic", "claude-haiku-4-5-20251001"),
}

# USD per million tokens (input, output). Kept as data so pricing updates are
# one-line edits; unknown models price at 0 and surface as "unpriced" in the
# dashboard rather than silently wrong.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-opus-4-8": (15.0, 75.0),
    "gemini-2.0-flash": (0.10, 0.40),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "deepseek-chat": (0.27, 1.10),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    inp, out = PRICING_PER_MTOK.get(model, (0.0, 0.0))
    return round((input_tokens * inp + output_tokens * out) / 1_000_000, 6)


@dataclass
class Route:
    provider: str
    model: str


def resolve_route(task: TaskType, project: Project | None = None,
                  db: Session | None = None) -> Route:
    """Priority: project override > global UI setting > code default."""
    provider, model = DEFAULT_ROUTES[task]
    if db is not None:
        from ..models import AppSetting

        row = db.get(AppSetting, "ai_routes")
        if row and row.value:
            ov = row.value.get(task.value) or {}
            provider = ov.get("provider", provider)
            model = ov.get("model", model)
    if project and project.ai_overrides:
        ov = project.ai_overrides.get(task.value) or {}
        provider = ov.get("provider", provider)
        model = ov.get("model", model)
    return Route(provider, model)


def _log(db: Session, resp: AIResponse, task: TaskType, *, project_id: str | None,
         chapter_id: str | None, agent: str | None, prompt_version: str | None,
         cache_hit: bool = False) -> AIRun:
    run = AIRun(
        project_id=project_id, chapter_id=chapter_id, task_type=task,
        provider=resp.provider, model=resp.model,
        input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
        estimated_cost_usd=estimate_cost_usd(resp.model, resp.input_tokens, resp.output_tokens),
        cache_hit=cache_hit, agent=agent, prompt_version=prompt_version,
    )
    db.add(run)
    db.commit()
    return run


def run_text(db: Session, task: TaskType, *, system: str, user: str,
             project: Project | None = None, chapter_id: str | None = None,
             agent: str | None = None, prompt_version: str | None = None,
             max_tokens: int = 4096, temperature: float = 0.7) -> AIResponse:
    route = resolve_route(task, project, db)
    resp = get_provider(route.provider).generate_text(
        system=system, user=user, model=route.model,
        max_tokens=max_tokens, temperature=temperature,
    )
    _log(db, resp, task, project_id=project.id if project else None,
         chapter_id=chapter_id, agent=agent, prompt_version=prompt_version)
    return resp


def run_image(db: Session, task: TaskType, *, system: str, image_path: Path,
              project: Project | None = None, agent: str | None = None,
              prompt_version: str | None = None) -> AIResponse:
    route = resolve_route(task, project, db)
    resp = get_provider(route.provider).classify_image(
        system=system, image_path=image_path, model=route.model,
    )
    _log(db, resp, task, project_id=project.id if project else None,
         chapter_id=None, agent=agent, prompt_version=prompt_version)
    return resp
