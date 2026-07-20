"""Google Drive v3 client — plain REST, no SDK. The transport is injectable
so every code path is unit-testable without credentials or network.

Drive is an optional sync target/source per project (§3), never a hard
dependency: everything works from local folders without it.
"""
from __future__ import annotations

import json
import mimetypes
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .google_auth import access_token

_API = "https://www.googleapis.com/drive/v3"
_UPLOAD = "https://www.googleapis.com/upload/drive/v3"


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int


def _default_transport(url: str, *, method: str = "GET", data: bytes | None = None,
                       headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    req.add_header("Authorization", f"Bearer {access_token()}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


class DriveClient:
    def __init__(self, transport: Callable[..., bytes] | None = None):
        self._t = transport or _default_transport

    def list_folder(self, folder_id: str) -> list[DriveFile]:
        """All non-trashed files directly inside a folder, across pages."""
        out: list[DriveFile] = []
        token = None
        while True:
            q = urllib.parse.urlencode({
                "q": f"'{folder_id}' in parents and trashed=false",
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "pageSize": 1000,
                **({"pageToken": token} if token else {}),
            })
            data = json.loads(self._t(f"{_API}/files?{q}"))
            for f in data.get("files", []):
                out.append(DriveFile(f["id"], f["name"], f.get("mimeType", ""),
                                     int(f.get("size", 0))))
            token = data.get("nextPageToken")
            if not token:
                return out

    def download(self, file_id: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(self._t(f"{_API}/files/{file_id}?alt=media"))
        return dest

    def ensure_folder(self, name: str, parent_id: str) -> str:
        """Find-or-create a subfolder; returns its id."""
        q = urllib.parse.urlencode({
            "q": (f"'{parent_id}' in parents and name='{name}' and "
                  "mimeType='application/vnd.google-apps.folder' and trashed=false"),
            "fields": "files(id)",
        })
        found = json.loads(self._t(f"{_API}/files?{q}")).get("files", [])
        if found:
            return found[0]["id"]
        body = json.dumps({"name": name, "parents": [parent_id],
                           "mimeType": "application/vnd.google-apps.folder"}).encode()
        created = json.loads(self._t(f"{_API}/files", method="POST", data=body,
                                     headers={"Content-Type": "application/json"}))
        return created["id"]

    def upload(self, local: Path, parent_id: str, name: str | None = None) -> str:
        """Multipart upload (replaces nothing — Drive allows duplicate names;
        callers that care overwrite by uploading into a fresh subfolder)."""
        name = name or local.name
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        boundary = "pbg-drive-upload"
        meta = json.dumps({"name": name, "parents": [parent_id]})
        payload = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
            f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n"
        ).encode() + local.read_bytes() + f"\r\n--{boundary}--".encode()
        created = json.loads(self._t(
            f"{_UPLOAD}/files?uploadType=multipart", method="POST", data=payload,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"}))
        return created["id"]


PHOTO_MIMES = {"image/jpeg", "image/png", "image/heic", "image/heif",
               "image/tiff", "image/webp"}
NOTE_EXTS = {".html", ".htm", ".json", ".docx", ".txt", ".md"}
MAP_EXTS = {".kml", ".geojson"}
