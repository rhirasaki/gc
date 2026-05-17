"""Thin Google Photos Library API client.

The library uses a two-step upload:
  1. POST raw bytes to /v1/uploads -> returns an upload token
  2. POST the upload token (+ optional album id) to
     /v1/mediaItems:batchCreate -> returns the persisted mediaItem

We expose `upload_one()` (bytes-only) and `batch_create()` (turn tokens
into media items). The uploader composes these per file and treats any
exception bubble-up as a per-file failure to be classified.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)


API_BASE = "https://photoslibrary.googleapis.com"
UPLOAD_URL = f"{API_BASE}/v1/uploads"
BATCH_CREATE_URL = f"{API_BASE}/v1/mediaItems:batchCreate"
USER_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SEARCH_URL = f"{API_BASE}/v1/mediaItems:search"


class PhotosAPIError(Exception):
    """Wraps an HTTP failure with the status code so retry.py can classify it."""

    def __init__(self, status_code: int, message: str):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


@dataclass
class UploadResult:
    google_photos_id: str
    product_url: Optional[str] = None


class GooglePhotosClient:
    def __init__(self, credentials):
        self._creds = credentials

    # -- info ----------------------------------------------------------

    def get_user_email(self, timeout: float = 10.0) -> Optional[str]:
        try:
            resp = requests.get(
                USER_INFO_URL,
                headers=self._auth_header(),
                timeout=timeout,
            )
            if resp.ok:
                return resp.json().get("email")
        except requests.RequestException:
            log.debug("get_user_email failed", exc_info=True)
        return None

    # -- upload --------------------------------------------------------

    def upload_one(
        self,
        path: Path,
        *,
        album_id: Optional[str] = None,
        description: Optional[str] = None,
        timeout: float = 300.0,
    ) -> UploadResult:
        """Upload a single file. Raises PhotosAPIError on HTTP failure."""
        upload_token = self._upload_bytes(path, timeout=timeout)
        return self._batch_create_single(
            upload_token, path.name, album_id=album_id,
            description=description, timeout=timeout,
        )

    def _upload_bytes(self, path: Path, *, timeout: float) -> str:
        size = path.stat().st_size
        headers = self._auth_header()
        headers.update({
            "Content-type": "application/octet-stream",
            "X-Goog-Upload-Content-Type": _guess_mime(path),
            "X-Goog-Upload-Protocol": "raw",
            "X-Goog-Upload-File-Name": path.name,
            "X-Goog-Upload-Raw-Size": str(size),
        })
        with path.open("rb") as f:
            resp = requests.post(UPLOAD_URL, headers=headers, data=f,
                                 timeout=timeout)
        if not resp.ok:
            raise PhotosAPIError(resp.status_code, resp.text[:500])
        token = resp.text.strip()
        if not token:
            raise PhotosAPIError(resp.status_code, "empty upload token")
        return token

    def _batch_create_single(
        self,
        upload_token: str,
        filename: str,
        *,
        album_id: Optional[str],
        description: Optional[str],
        timeout: float,
    ) -> UploadResult:
        item: dict = {
            "simpleMediaItem": {
                "fileName": filename,
                "uploadToken": upload_token,
            },
        }
        if description:
            item["description"] = description

        body: dict = {"newMediaItems": [item]}
        if album_id:
            body["albumId"] = album_id

        resp = requests.post(
            BATCH_CREATE_URL,
            headers={**self._auth_header(), "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
        if not resp.ok:
            raise PhotosAPIError(resp.status_code, resp.text[:500])

        data = resp.json()
        results = data.get("newMediaItemResults") or []
        if not results:
            raise PhotosAPIError(resp.status_code, "no result in batchCreate")
        first = results[0]
        status = first.get("status") or {}
        # status.code: 0 = OK in google.rpc.Code; absent also means success.
        if status.get("code") not in (None, 0):
            raise PhotosAPIError(500, status.get("message") or "batchCreate failed")
        media = first.get("mediaItem") or {}
        gid = media.get("id")
        if not gid:
            raise PhotosAPIError(500, "missing mediaItem.id")
        return UploadResult(
            google_photos_id=gid,
            product_url=media.get("productUrl"),
        )

    # -- verification --------------------------------------------------

    def media_item_exists(self, media_id: str, timeout: float = 15.0) -> bool:
        try:
            resp = requests.get(
                f"{API_BASE}/v1/mediaItems/{media_id}",
                headers=self._auth_header(),
                timeout=timeout,
            )
        except requests.RequestException:
            return False
        return resp.ok

    # -- helpers -------------------------------------------------------

    def _auth_header(self) -> dict:
        token = self._refresh_if_needed()
        return {"Authorization": f"Bearer {token}"}

    def _refresh_if_needed(self) -> str:
        creds = self._creds
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        if not creds.token:
            raise PhotosAPIError(401, "no access token available")
        return creds.token


def _guess_mime(path: Path) -> str:
    import mimetypes
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"
