"""State-machine legality."""

import pytest

from photo_manager.models import PhotoStatus, can_transition


@pytest.mark.parametrize("src,dst,ok", [
    (PhotoStatus.INBOX, PhotoStatus.PENDING, True),
    (PhotoStatus.PENDING, PhotoStatus.UPLOADING, True),
    (PhotoStatus.UPLOADING, PhotoStatus.UPLOADED, True),
    (PhotoStatus.UPLOADING, PhotoStatus.PENDING, True),   # transient
    (PhotoStatus.UPLOADING, PhotoStatus.FAILED, True),    # permanent
    (PhotoStatus.FAILED, PhotoStatus.PENDING, True),      # manual retry
    (PhotoStatus.UPLOADED, PhotoStatus.PENDING, False),   # terminal
    (PhotoStatus.INBOX, PhotoStatus.UPLOADING, False),    # must go through Pending
    (PhotoStatus.PENDING, PhotoStatus.UPLOADED, False),
])
def test_transitions(src, dst, ok):
    assert can_transition(src, dst) is ok
