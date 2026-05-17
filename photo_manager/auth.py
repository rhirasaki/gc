"""Google OAuth flow with OS-keychain token storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Google Photos Library API scopes.
# Note: as of 2025, the upload scope is `photoslibrary.appendonly`. For
# reading user info, OpenID's `userinfo.email` is sufficient.
SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.appendonly",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

KEYRING_SERVICE = "PhotoManager"
KEYRING_USER = "google-oauth-token"


def load_credentials(client_secret_path: Path) -> "Credentials":
    """Return Google OAuth credentials, running the browser flow if needed."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = _load_from_keyring()
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_to_keyring(creds)
            return creds
        except Exception as e:
            log.warning("Token refresh failed, re-authenticating: %s", e)

    return run_flow(client_secret_path)


def run_flow(client_secret_path: Path) -> "Credentials":
    """Interactive OAuth flow (opens browser)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not client_secret_path.exists():
        raise FileNotFoundError(
            f"OAuth client_secret not found at {client_secret_path}. "
            "Create one in Google Cloud Console (Desktop app) and point "
            "Settings → OAuth client at it."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    _save_to_keyring(creds)
    return creds


def clear_credentials() -> None:
    try:
        import keyring
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass


def _save_to_keyring(creds) -> None:
    try:
        import keyring
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, creds.to_json())
    except Exception as e:
        log.warning("Could not store token in OS keyring: %s. "
                    "Falling back to plaintext on disk.", e)
        _save_to_disk(creds)


def _load_from_keyring() -> Optional["Credentials"]:
    from google.oauth2.credentials import Credentials
    try:
        import keyring
        raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        raw = None
    if not raw:
        raw = _load_from_disk()
    if not raw:
        return None
    try:
        return Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    except Exception as e:
        log.warning("Stored token unreadable: %s", e)
        return None


def _disk_token_path() -> Path:
    from .config import data_dir
    return data_dir() / "token.json"


def _save_to_disk(creds) -> None:
    path = _disk_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_json())
    # POSIX-only chmod; best-effort.
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _load_from_disk() -> Optional[str]:
    path = _disk_token_path()
    if not path.exists():
        return None
    try:
        return path.read_text()
    except OSError:
        return None
