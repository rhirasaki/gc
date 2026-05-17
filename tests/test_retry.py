"""Error classification and backoff schedule."""

import pytest

from photo_manager.models import ErrorKind
from photo_manager.retry import (
    BACKOFF_SCHEDULE, classify_exception, classify_http, next_delay, should_retry,
)


@pytest.mark.parametrize("code,kind", [
    (401, ErrorKind.PERMANENT),
    (403, ErrorKind.PERMANENT),
    (404, ErrorKind.PERMANENT),
    (413, ErrorKind.PERMANENT),
    (429, ErrorKind.TRANSIENT),
    (500, ErrorKind.TRANSIENT),
    (503, ErrorKind.TRANSIENT),
    (504, ErrorKind.TRANSIENT),
])
def test_classify_http(code, kind):
    assert classify_http(code).kind == kind


def test_classify_timeout_exception():
    err = classify_exception(TimeoutError("read timed out"))
    assert err.kind == ErrorKind.TRANSIENT


def test_classify_connection_error():
    err = classify_exception(ConnectionError("nope"))
    assert err.kind == ErrorKind.TRANSIENT


def test_classify_permanent_signal():
    err = classify_exception(Exception("quota exceeded for project"))
    assert err.kind == ErrorKind.PERMANENT


def test_backoff_schedule_increases():
    delays = [next_delay(i) for i in range(1, 8)]
    # Monotonic until the cap.
    assert delays[0] == BACKOFF_SCHEDULE[0]
    assert delays[-1] == BACKOFF_SCHEDULE[-1]
    for a, b in zip(delays, delays[1:]):
        assert b >= a


def test_should_retry_respects_max():
    transient = classify_http(503)
    assert should_retry(transient, attempt_count=1, max_retries=5)
    assert not should_retry(transient, attempt_count=5, max_retries=5)
    permanent = classify_http(403)
    assert not should_retry(permanent, attempt_count=0, max_retries=5)
