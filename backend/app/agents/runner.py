"""Agent runner: loads versioned system prompts from backend/prompts/, calls
through the AI router (so every run is logged/priced), and validates the JSON
contract. Prompt files are the auditable source of truth — never inline
prompt text in application code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Project, TaskType
from ..ai.router import run_image, run_text

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass(frozen=True)
class AgentPrompt:
    name: str
    version: str
    system: str


@lru_cache(maxsize=32)
def load_prompt(agent_name: str) -> AgentPrompt:
    path = settings.prompts_root / f"{agent_name}_agent.md"
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    version = "0.0.0"
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("version:"):
                version = line.split(":", 1)[1].strip()
        text = text[m.end():]
    return AgentPrompt(name=agent_name, version=version, system=text.strip())


TASK_FOR_AGENT: dict[str, TaskType] = {
    "classification": TaskType.classification,
    "narrative_writer": TaskType.narrative,
    "research": TaskType.research,
    "grounding": TaskType.grounding,
    "chat_orchestrator": TaskType.chat,
    "ingestion": TaskType.ingestion,
    "layout": TaskType.layout,
}


def run_agent(db: Session, agent_name: str, user_payload: str, *,
              project: Project | None = None, chapter_id: str | None = None,
              max_tokens: int = 4096, temperature: float = 0.3) -> dict:
    """Text agent call -> parsed JSON per the agent's contract."""
    prompt = load_prompt(agent_name)
    resp = run_text(
        db, TASK_FOR_AGENT[agent_name], system=prompt.system, user=user_payload,
        project=project, chapter_id=chapter_id, agent=agent_name,
        prompt_version=prompt.version, max_tokens=max_tokens, temperature=temperature,
    )
    return resp.json()


def run_image_agent(db: Session, agent_name: str, image_path: Path, *,
                    project: Project | None = None) -> dict:
    prompt = load_prompt(agent_name)
    resp = run_image(
        db, TASK_FOR_AGENT[agent_name], system=prompt.system, image_path=image_path,
        project=project, agent=agent_name, prompt_version=prompt.version,
    )
    return resp.json()
