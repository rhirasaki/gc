"""Data model (§4 of the spec).

Design notes:
- Assets are linked to chapters through ChapterAsset rows so a photo swap
  touches exactly one link row + one chapter dirty flag — never a cascade.
- Chapter mirrors the MANIFEST.json shape from the reference project:
  label, ordered assets, narrative, page range, changed_since_final.
- AIRun logs every AI call; it is the backbone of the cost dashboard and the
  reason token spend is visible as COGS.
- Manual edits set *_manual_override flags so re-runs never silently clobber
  a human decision.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, enum.Enum):
    intake = "intake"
    drafting = "drafting"
    review = "review"
    final = "final"
    delivered = "delivered"


class NoteSource(str, enum.Enum):
    apple_notes = "apple_notes"
    google_keep = "google_keep"
    word = "word"
    txt = "txt"
    pasted = "pasted"


class AssetRole(str, enum.Enum):
    hero = "hero"
    detail = "detail"
    candid = "candid"
    unassigned = "unassigned"


class TaskType(str, enum.Enum):
    classification = "classification"
    narrative = "narrative"
    research = "research"
    chat = "chat"
    grounding = "grounding"
    synopsis = "synopsis"
    layout = "layout"
    ingestion = "ingestion"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    referral_source: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    projects: Mapped[list[Project]] = relationship(back_populates="client")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    trip_name: Mapped[str] = mapped_column(String(300))
    destinations: Mapped[list | None] = mapped_column(JSON, default=list)
    date_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trip_reason: Mapped[str | None] = mapped_column(String(200))  # anniversary, graduation, ...
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.intake, index=True
    )
    template_id: Mapped[str | None] = mapped_column(ForeignKey("templates.id"))
    # Storage config: local path is source of truth; Drive is optional sync.
    input_path: Mapped[str | None] = mapped_column(String(1000))
    output_path: Mapped[str | None] = mapped_column(String(1000))
    drive_folder_id: Mapped[str | None] = mapped_column(String(200))
    # Rolling dashboard summary
    synopsis: Mapped[str | None] = mapped_column(Text)  # short AI-generated story synopsis
    sale_price_usd: Mapped[float] = mapped_column(Float, default=2500.0)
    images_per_chapter: Mapped[int] = mapped_column(Integer, default=10)
    # Per-project AI settings overrides: {task_type: {"provider":..., "model":...}}
    ai_overrides: Mapped[dict | None] = mapped_column(JSON, default=dict)
    # Coastal/Tropical templates key accents to sampled photo palette.
    sampled_palette: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    client: Mapped[Client] = relationship(back_populates="projects")
    template: Mapped[Template | None] = relationship()
    assets: Mapped[list[Asset]] = relationship(back_populates="project")
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="project", order_by="Chapter.position"
    )
    notes_items: Mapped[list[Note]] = relationship(back_populates="project")
    map_pins: Mapped[list[MapPin]] = relationship(back_populates="project")


class Asset(Base):
    """A photo. Original untouched on disk; working derivative used in drafts;
    high-res swapped in only by the Finalize Images job."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    original_path: Mapped[str] = mapped_column(String(1000))
    working_path: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)  # classification cache key
    perceptual_hash: Mapped[str | None] = mapped_column(String(32), index=True)
    finalized: Mapped[bool] = mapped_column(Boolean, default=False)  # high-res swapped in

    exif: Mapped[dict | None] = mapped_column(JSON)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    gps_lat: Mapped[float | None] = mapped_column(Float)
    gps_lng: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    aspect_class: Mapped[str | None] = mapped_column(String(20))  # 16:9, 4:3, 3:2, square, portrait-tall...

    # Local heuristics (no tokens spent)
    blur_score: Mapped[float | None] = mapped_column(Float)
    composition_score: Mapped[float | None] = mapped_column(Float)  # rule-of-thirds, 0..1
    duplicate_of: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))

    # AI classification — cached forever keyed on content_hash.
    classification: Mapped[dict | None] = mapped_column(JSON)  # subjects, scene, quality, role
    suggested_role: Mapped[AssetRole] = mapped_column(Enum(AssetRole), default=AssetRole.unassigned)
    classified_by_provider: Mapped[str | None] = mapped_column(String(50))
    classified_by_model: Mapped[str | None] = mapped_column(String(100))
    classified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)  # human edit wins, never clobbered

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    project: Mapped[Project] = relationship(back_populates="assets")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_type: Mapped[NoteSource] = mapped_column(Enum(NoteSource))
    title: Mapped[str | None] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)  # normalized plain text
    noted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)

    project: Mapped[Project] = relationship(back_populates="notes_items")


class MapPin(Base):
    __tablename__ = "map_pins"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    place_name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str | None] = mapped_column(String(100))  # restaurant, trailhead, viewpoint...
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(50))  # places_api, kml, geojson
    raw_metadata: Mapped[dict | None] = mapped_column(JSON)

    project: Mapped[Project] = relationship(back_populates="map_pins")


class Chapter(Base):
    """One unit of the book (a day or a theme). Mirrors the MANIFEST.json shape."""

    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)  # order in the book
    label: Mapped[str] = mapped_column(String(300))  # "Day 3 — Reykjavik" or theme
    narrative: Mapped[str | None] = mapped_column(Text)
    narrative_tone: Mapped[str | None] = mapped_column(String(100))
    research_context: Mapped[dict | None] = mapped_column(JSON)  # cited historical/geo facts
    grounding_report: Mapped[dict | None] = mapped_column(JSON)  # flagged ungrounded sentences
    layout_plan: Mapped[dict | None] = mapped_column(JSON)  # chosen layout variants per page
    template_variant_override: Mapped[str | None] = mapped_column(String(100))
    pinned_hero_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"))  # escape hatch: removed from auto-selection
    # Set after a Final render; the preview stitch uses cached per-chapter PDFs.
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    changed_since_final: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    rendered_pdf_path: Mapped[str | None] = mapped_column(String(1000))
    rendered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="chapters")
    chapter_assets: Mapped[list[ChapterAsset]] = relationship(
        back_populates="chapter", order_by="ChapterAsset.position", cascade="all, delete-orphan"
    )

    def mark_dirty(self) -> None:
        self.changed_since_final = True


class ChapterAsset(Base):
    """Ordered link between a chapter and an asset. A photo swap replaces one
    of these rows and dirties one chapter — nothing else."""

    __tablename__ = "chapter_assets"
    __table_args__ = (UniqueConstraint("chapter_id", "position"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    chapter_id: Mapped[str] = mapped_column(ForeignKey("chapters.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    layout_hint: Mapped[str | None] = mapped_column(String(50))  # pf-tall, pf-sm, feature-clean...

    chapter: Mapped[Chapter] = relationship(back_populates="chapter_assets")
    asset: Mapped[Asset] = relationship()


class Template(Base):
    """Reusable across projects. Built-ins are seeded from templates/ on disk;
    custom templates store their token overrides + page-type component config."""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # slug
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    base_template_id: Mapped[str | None] = mapped_column(ForeignKey("templates.id"))  # custom clones point at a builtin
    tokens: Mapped[dict | None] = mapped_column(JSON)  # design-token overrides (color/type/grid)
    # Per page-type component tree config: which elements appear, order, toggles.
    page_config: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AppSetting(Base):
    """Global key/value config editable from the UI (AI routing per task type,
    budget alerts) — no config-file editing for routine workflows (§1)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | None] = mapped_column(JSON)


class AIRun(Base):
    """Every AI call. Token cost is COGS; this table is the cost dashboard."""

    __tablename__ = "ai_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("chapters.id"), index=True)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), index=True)
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    agent: Mapped[str | None] = mapped_column(String(50))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class ChangeLog(Base):
    """Chat-triggered and UI-triggered changes, logged per project/chapter so
    edits are visible and cheap to undo."""

    __tablename__ = "change_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("chapters.id"), index=True)
    tool: Mapped[str] = mapped_column(String(50))  # swap_asset, regenerate_narrative, ...
    args: Mapped[dict | None] = mapped_column(JSON)
    undo_state: Mapped[dict | None] = mapped_column(JSON)  # snapshot to restore on undo
    source: Mapped[str] = mapped_column(String(20), default="chat")  # chat | ui
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class Job(Base):
    """Background job rows (renders, finalize-images, classification batches).
    The queue backend is pluggable; state of record lives here either way."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50), index=True)  # render_final, render_preview, finalize_images, classify_batch, cleanup
    params: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued, index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    progress_note: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
