"""Google OAuth for Drive: refresh-token flow, pure HTTP.

A solo operator connects once (any OAuth playground or the gcloud CLI can mint
a refresh token for their own account) and sets three env vars:

    PBG_GDRIVE_CLIENT_ID / PBG_GDRIVE_CLIENT_SECRET / PBG_GDRIVE_REFRESH_TOKEN

Access tokens are minted lazily and cached until near expiry. For dev/test,
PBG_GDRIVE_ACCESS_TOKEN short-circuits the flow entirely.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_cache: dict = {"token": None, "expires": 0.0}


class DriveNotConfigured(RuntimeError):
    """Raised when Drive credentials are absent — callers surface this as a
    clean 'not connected' state, never a stack trace."""


def configured() -> bool:
    return bool(os.environ.get("PBG_GDRIVE_ACCESS_TOKEN") or (
        os.environ.get("PBG_GDRIVE_CLIENT_ID")
        and os.environ.get("PBG_GDRIVE_CLIENT_SECRET")
        and os.environ.get("PBG_GDRIVE_REFRESH_TOKEN")))


def access_token() -> str:
    direct = os.environ.get("PBG_GDRIVE_ACCESS_TOKEN")
    if direct:
        return direct
    if not configured():
        raise DriveNotConfigured(
            "Google Drive is not connected. Set PBG_GDRIVE_CLIENT_ID, "
            "PBG_GDRIVE_CLIENT_SECRET and PBG_GDRIVE_REFRESH_TOKEN.")
    if _cache["token"] and time.time() < _cache["expires"] - 60:
        return _cache["token"]
    body = urllib.parse.urlencode({
        "client_id": os.environ["PBG_GDRIVE_CLIENT_ID"],
        "client_secret": os.environ["PBG_GDRIVE_CLIENT_SECRET"],
        "refresh_token": os.environ["PBG_GDRIVE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(_TOKEN_URL, data=body,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    _cache["token"] = data["access_token"]
    _cache["expires"] = time.time() + float(data.get("expires_in", 3600))
    return _cache["token"]
