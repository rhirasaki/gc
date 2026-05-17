"""Core domain models and the photo state machine.

A photo lives in exactly one folder state at a time:

    Inbox --(user flags)--> Pending --(scheduler picks up)--> Uploading
        |                                                          |
        |                                          success ----> Uploaded
        |                                          permanent ---> Failed
        |                                          transient --> Pending (retry)

State transitions are atomic: the DB row and the on-disk file location
are always updated together. The transition rules below are enforced by
the uploader; the model here just defines what's legal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class PhotoStatus(str, Enum):
    INBOX = "inbox"
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    FAILED = "failed"


# Allowed forward transitions. Anything not in this map is rejected.
_TRANSITIONS: dict[PhotoStatus, set[PhotoStatus]] = {
    PhotoStatus.INBOX: {PhotoStatus.PENDING, PhotoStatus.FAILED},
    PhotoStatus.PENDING: {PhotoStatus.UPLOADING, PhotoStatus.INBOX},
    PhotoStatus.UPLOADING: {
        PhotoStatus.UPLOADED,
        PhotoStatus.PENDING,  # transient failure / timeout
        PhotoStatus.FAILED,   # permanent failure
    },
    PhotoStatus.FAILED: {PhotoStatus.PENDING},  # manual "Retry All Failed"
    PhotoStatus.UPLOADED: set(),  # terminal
}


def can_transition(src: PhotoStatus, dst: PhotoStatus) -> bool:
    return dst in _TRANSITIONS.get(src, set())


class ErrorKind(str, Enum):
    """Classification used to decide retry vs. give-up."""

    TRANSIENT = "transient"   # network, 5xx, 429, timeout — retry
    PERMANENT = "permanent"   # 401/403/404, quota — do not retry
    UNKNOWN = "unknown"       # treat as transient but cap retries hard


@dataclass
class Photo:
    id: Optional[int]
    filename: str
    filepath: str
    status: PhotoStatus
    date_added: datetime
    date_uploaded: Optional[datetime] = None
    attempt_count: int = 0
    last_attempt_timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    google_photos_id: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    date_taken: Optional[datetime] = None
    camera_model: Optional[str] = None
    exif_json: Optional[str] = None
