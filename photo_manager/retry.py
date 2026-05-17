"""Error classification and exponential backoff.

Two responsibilities:
  - decide whether a given failure is transient (worth retrying) or
    permanent (stop and surface to the user);
  - compute the next delay given the attempt number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .models import ErrorKind


# Backoff schedule in seconds: retry 1 at 60s, then 5m, 15m, 45m, 2h.
# Capped at max_retries; index = attempt_count just completed.
BACKOFF_SCHEDULE = [60, 300, 900, 2700, 7200]


def next_delay(attempt_count: int) -> int:
    if attempt_count <= 0:
        return BACKOFF_SCHEDULE[0]
    idx = min(attempt_count - 1, len(BACKOFF_SCHEDULE) - 1)
    return BACKOFF_SCHEDULE[idx]


@dataclass
class ClassifiedError:
    kind: ErrorKind
    code: str
    message: str


# HTTP codes treated as permanent. Anything else -> transient (worth retrying).
PERMANENT_HTTP = {400, 401, 403, 404, 410, 413, 415}


def classify_http(status_code: int, message: str = "") -> ClassifiedError:
    if status_code in PERMANENT_HTTP:
        return ClassifiedError(ErrorKind.PERMANENT, f"HTTP_{status_code}", message)
    # 429 (rate limit), 5xx, anything else -> transient.
    return ClassifiedError(ErrorKind.TRANSIENT, f"HTTP_{status_code}", message)


def classify_exception(exc: BaseException) -> ClassifiedError:
    """Best-effort classification from exception type/text."""
    name = exc.__class__.__name__
    msg = str(exc)
    lowered = msg.lower()

    if "quota" in lowered or "storage" in lowered and "full" in lowered:
        return ClassifiedError(ErrorKind.PERMANENT, "QUOTA_EXCEEDED", msg)
    if "permission" in lowered or "forbidden" in lowered:
        return ClassifiedError(ErrorKind.PERMANENT, "PERMISSION_DENIED", msg)
    if "auth" in lowered and "expired" not in lowered:
        return ClassifiedError(ErrorKind.PERMANENT, "AUTH_FAILED", msg)
    if "not found" in lowered or "no such file" in lowered:
        return ClassifiedError(ErrorKind.PERMANENT, "NOT_FOUND", msg)
    if name in {"TimeoutError", "ConnectionError", "ConnectionResetError",
                "ConnectionAbortedError", "OSError"}:
        return ClassifiedError(ErrorKind.TRANSIENT, "NETWORK", msg)
    if "timeout" in lowered or "timed out" in lowered:
        return ClassifiedError(ErrorKind.TRANSIENT, "TIMEOUT", msg)
    return ClassifiedError(ErrorKind.UNKNOWN, "UNKNOWN", msg)


def should_retry(err: ClassifiedError, attempt_count: int, max_retries: int) -> bool:
    if err.kind == ErrorKind.PERMANENT:
        return False
    return attempt_count < max_retries
