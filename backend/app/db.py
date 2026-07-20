from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str | None = None):
    url = url or settings.db_url
    if url.startswith("sqlite"):
        db_path = url.replace("sqlite:///", "")
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA journal_mode=WAL")

        return engine
    # Postgres path stays open: same models, no SQLite-isms in the schema.
    return create_engine(url, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    import json

    from . import models  # noqa: F401 — register mappings

    Base.metadata.create_all(engine)
    # Additive mini-migrations for SQLite (create_all never alters existing
    # tables). Each entry is idempotent — the ALTER fails harmlessly if the
    # column already exists.
    from sqlalchemy import text

    for ddl in ("ALTER TABLE assets ADD COLUMN composition_score FLOAT",):
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception:  # noqa: BLE001 — column already present
            pass
    # Seed builtin template rows from the on-disk registry so FKs resolve.
    registry_path = settings.templates_root / "registry.json"
    if registry_path.exists():
        registry = json.loads(registry_path.read_text())
        with SessionLocal() as db:
            for t in registry["templates"]:
                if db.get(models.Template, t["id"]) is None:
                    db.add(models.Template(id=t["id"], name=t["name"],
                                           description=t.get("description"),
                                           builtin=True, page_config=t.get("page_config")))
            db.commit()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
