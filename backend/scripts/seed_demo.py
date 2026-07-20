"""Seed the default DB with a realistic demo commission (photos, chapters,
narratives, fake cost ledger) so the UI has something true to show.

Run: python -m scripts.seed_demo
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

from app.config import settings
from app.db import SessionLocal, init_db
from app.models import AIRun, Client, MapPin, Project, TaskType
from app.services.ingest import import_notes, import_photos, propose_day_chapters
from scripts.demo_e2e import make_demo_photos


def main() -> None:
    init_db()
    db = SessionLocal()
    if db.query(Project).count():
        print("DB already seeded")
        return
    src = settings.data_root.parent / "demo_camera_roll"
    if not src.exists():
        make_demo_photos(src, days=4, per_day=6)

    client = Client(name="The Harrison Family", email="harrisons@example.com",
                    referral_source="Returning client")
    db.add(client)
    db.flush()
    project = Project(
        client_id=client.id, trip_name="Iceland, Together",
        destinations=["Reykjavik", "Vik", "Höfn"],
        date_start=datetime(2025, 6, 10, tzinfo=timezone.utc),
        date_end=datetime(2025, 6, 14, tzinfo=timezone.utc),
        trip_reason="25th anniversary", template_id="heritage-journal",
        input_path=str(src), sale_price_usd=2800,
        synopsis="Five June days across the south coast — harbor mornings in Reykjavik, "
                 "the black sand at Vik, and a night the sky finally cleared.",
    )
    db.add(project)
    db.commit()

    import_photos(db, project, src)
    import_notes(db, project, pasted=(
        "Day 1: Landed early, lobster soup at the old harbor. Kids fed the ducks at Tjörnin.\n"
        "Day 2: Drove to Vik. Black sand beach, basalt columns. Anna found a puffin colony.\n"
        "Day 3: Glacier lagoon at Jökulsárlón, seals in the ice.\n"
        "Day 4: Northern lights over the guesthouse at 1am — everyone out in socks."))
    db.add(MapPin(project_id=project.id, place_name="Blue Lagoon", category="spa",
                  lat=63.8804, lng=-22.4495, source="kml"))
    db.add(MapPin(project_id=project.id, place_name="Reynisfjara Beach", category="viewpoint",
                  lat=63.4064, lng=-19.0439, source="kml"))
    db.commit()
    propose_day_chapters(db, project)
    db.refresh(project)

    narratives = [
        "The trip began the way the best ones do — early, hungry, and a little lost. "
        "By mid-morning the harbor had sorted everyone out: lobster soup in paper cups, "
        "ducks at Tjörnin negotiating for bread.",
        "South along the coast the weather turned theatrical. At Reynisfjara the sand is "
        "actually black, the basalt actually hexagonal, and Anna — first to the cliff path — "
        "found the puffins before the guidebook did.",
        "Jökulsárlón moves slower than anything else on the itinerary. Icebergs the size of "
        "houses drift toward the sea while seals patrol between them like harbor masters.",
        "At one in the morning someone knocked on every door, and the whole family stood out "
        "on the deck in wool socks while the sky went green from one horizon to the other.",
    ]
    for ch, text in zip(sorted(project.chapters, key=lambda c: c.position), narratives):
        ch.narrative = text
    ch = sorted(project.chapters, key=lambda c: c.position)[1]
    ch.grounding_report = {"ungrounded_count": 2,
                          "summary": "2 sentences aren't grounded in your notes or photo metadata — review before finalizing."}
    db.commit()

    # Fake cost ledger so the dashboard shows real shapes.
    runs = [
        (TaskType.classification, "anthropic", "claude-haiku-4-5-20251001", 24, 210000, 41000, 0.42),
        (TaskType.narrative, "anthropic", "claude-sonnet-5", 4, 60000, 9800, 0.33),
        (TaskType.research, "anthropic", "claude-sonnet-5", 1, 4200, 2600, 0.05),
        (TaskType.grounding, "anthropic", "claude-haiku-4-5-20251001", 4, 30000, 6000, 0.06),
        (TaskType.chat, "anthropic", "claude-haiku-4-5-20251001", 11, 15000, 1500, 0.02),
    ]
    for task, prov, model, n, tin, tout, cost in runs:
        for _ in range(n):
            db.add(AIRun(project_id=project.id, task_type=task, provider=prov, model=model,
                         input_tokens=tin // n, output_tokens=tout // n,
                         estimated_cost_usd=cost / n))
    for _ in range(9):
        db.add(AIRun(project_id=project.id, task_type=TaskType.classification,
                     provider="cache", model="cache", cache_hit=True))
    db.commit()
    print(f"Seeded project {project.id}")


if __name__ == "__main__":
    main()
