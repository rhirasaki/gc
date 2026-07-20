"""Drive <-> project sync jobs.

Pull: download the project's Drive folder (photos + note files + map exports)
into a local inbox, then run the exact same local import pipeline — Drive is
a transport, never a second code path.

Push: upload rendered PDFs into a "Rendered" subfolder of the project's
Drive folder.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..integrations.drive import (DriveClient, MAP_EXTS, NOTE_EXTS, PHOTO_MIMES)
from ..models import Project
from ..rendering.book import project_dirs
from . import ingest as ingest_svc


def pull_from_drive(db: Session, project: Project, progress=lambda f, n: None,
                    client: DriveClient | None = None) -> dict:
    if not project.drive_folder_id:
        raise ValueError("This project has no Drive folder configured.")
    client = client or DriveClient()
    dirs = project_dirs(project.id)
    inbox = dirs["root"] / "drive_inbox"

    files = client.list_folder(project.drive_folder_id)
    photos = [f for f in files if f.mime_type in PHOTO_MIMES]
    notes = [f for f in files if Path(f.name).suffix.lower() in NOTE_EXTS]
    maps = [f for f in files if Path(f.name).suffix.lower() in MAP_EXTS]

    total = len(photos) + len(notes) + len(maps)
    done = 0
    for f in photos:
        client.download(f.id, inbox / "photos" / f.name)
        done += 1
        progress(0.7 * done / max(total, 1), f"Downloaded {f.name}")
    note_paths, map_paths = [], []
    for f in notes:
        note_paths.append(client.download(f.id, inbox / "notes" / f.name))
        done += 1
    for f in maps:
        map_paths.append(client.download(f.id, inbox / "maps" / f.name))
        done += 1

    progress(0.75, "Importing photos")
    photo_result = (ingest_svc.import_photos(db, project, inbox / "photos")
                    if photos else {"imported": 0})
    notes_n = ingest_svc.import_notes(db, project, note_paths) if note_paths else 0
    pins_n = sum(ingest_svc.import_map_pins(db, project, p) for p in map_paths)
    progress(1.0, "Drive pull complete")
    return {"photos": photo_result.get("imported", 0), "notes": notes_n,
            "pins": pins_n, "drive_files_seen": len(files)}


def push_to_drive(db: Session, project: Project, progress=lambda f, n: None,
                  client: DriveClient | None = None) -> dict:
    if not project.drive_folder_id:
        raise ValueError("This project has no Drive folder configured.")
    client = client or DriveClient()
    rendered = project_dirs(project.id)["rendered"]
    pdfs = [p for p in (rendered / "book_final.pdf", rendered / "book_preview.pdf")
            if p.exists()]
    if not pdfs:
        raise ValueError("Nothing rendered yet — render a preview or final first.")
    folder = client.ensure_folder("Rendered", project.drive_folder_id)
    uploaded = []
    for i, pdf in enumerate(pdfs):
        name = f"{project.trip_name} — {pdf.stem.replace('book_', '')}.pdf"
        client.upload(pdf, folder, name)
        uploaded.append(name)
        progress((i + 1) / len(pdfs), f"Uploaded {name}")
    return {"uploaded": uploaded, "folder_id": folder}
