from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .db import init_db

app = FastAPI(title="Photo Book Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    _start_cleanup_scheduler()


def _start_cleanup_scheduler() -> None:
    """Periodic artifact sweep across all projects (§12) — the scheduled half
    of cleanup; the user-triggered half is the per-project endpoint/chat tool."""
    import threading
    import time

    from .config import settings
    from .db import SessionLocal
    from .models import Project
    from .rendering.book import cleanup_artifacts

    if settings.cleanup_interval_hours <= 0:
        return

    def loop() -> None:
        while True:
            time.sleep(settings.cleanup_interval_hours * 3600)
            db = SessionLocal()
            try:
                for (pid,) in db.query(Project.id).all():
                    try:
                        cleanup_artifacts(pid)
                    except OSError:
                        continue
            finally:
                db.close()

    threading.Thread(target=loop, name="pbg-cleanup", daemon=True).start()


@app.get("/health")
def health():
    return {"ok": True}
