"""Application settings.

Every operational threshold that the reference project learned the hard way
(chunking threshold, disk headroom, derivative size) is a tunable here, not a
constant buried in the rendering code.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PBG_", env_file=".env", extra="ignore")

    # Storage roots. Each project gets data_root/<project_id>/{originals,working,chapters,rendered}
    data_root: Path = Path("data/projects")
    db_url: str = "sqlite:///data/photobook.db"
    templates_root: Path = Path(__file__).resolve().parent.parent.parent / "templates"
    prompts_root: Path = Path(__file__).resolve().parent.parent / "prompts"

    # Rendering (see rendering/engine.py). chunk_threshold_mb: once a book's
    # assembled payload exceeds this, chunked one-process-per-chunk rendering
    # engages automatically. ~200MB was the measured figure in the reference
    # project; tunable, never hard-coded at call sites.
    chunk_threshold_mb: int = 200
    chunk_pages: int = 12                  # pages per chunk in chunked fallback
    min_free_disk_gb: float = 5.0          # preflight fail-fast floor
    require_swap: bool = True              # preflight: require active swap for heavy renders
    heavy_render_payload_mb: int = 100     # payload size above which a render counts as "heavy"
    render_timeout_s: int = 600
    # Explicit Chromium binary (e.g. a system/preinstalled build). Empty means
    # let Playwright resolve its own managed browser.
    chromium_executable: str = ""

    # Photo pipeline
    working_long_edge_px: int = 1600       # draft derivative size; originals are never embedded in drafts
    derivative_quality: int = 85
    near_duplicate_phash_distance: int = 6

    # Book defaults
    images_per_chapter_min: int = 5
    images_per_chapter_max: int = 15
    default_template: str = "heritage-journal"

    # AI / cost
    token_budget_alert_usd: float = 50.0   # per-project alert threshold
    default_book_price_usd: float = 2500.0

    # Job queue: "local" (thread pool, zero external deps) or "rq" (Redis).
    job_backend: str = "local"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
