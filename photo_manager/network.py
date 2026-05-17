"""Connectivity detection.

We probe `https://www.googleapis.com/generate_204` — same idiom Chrome uses
for captive-portal detection — which returns 204 quickly and works behind
proxies. Failure of the probe means "treat as offline"; the uploader pauses
and we retry the probe on an interval.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

PROBE_URL = "https://www.googleapis.com/generate_204"
DEFAULT_TIMEOUT_SEC = 5


def is_online(timeout: float = DEFAULT_TIMEOUT_SEC) -> bool:
    """Quick boolean check.

    Tries a HEAD on the probe URL; falls back to DNS resolution so we
    still get a sane answer if `requests` isn't importable yet.
    """
    try:
        import requests
        resp = requests.head(PROBE_URL, timeout=timeout, allow_redirects=False)
        return resp.status_code in (204, 200, 301, 302)
    except Exception:
        pass
    try:
        socket.gethostbyname("www.googleapis.com")
        return True
    except OSError:
        return False


class NetworkMonitor:
    """Polls connectivity in a background thread and fires callbacks on
    state transitions. Cheap: one HEAD request every N seconds."""

    def __init__(
        self,
        interval_sec: int = 30,
        on_change: Optional[Callable[[bool], None]] = None,
    ):
        self.interval_sec = interval_sec
        self.on_change = on_change
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._online = True  # optimistic start

    @property
    def online(self) -> bool:
        return self._online

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                         name="network-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        # Initial probe.
        self._update(is_online())
        while not self._stop.wait(self.interval_sec):
            self._update(is_online())

    def _update(self, online: bool) -> None:
        if online != self._online:
            log.info("Network %s", "online" if online else "offline")
            self._online = online
            if self.on_change:
                try:
                    self.on_change(online)
                except Exception:
                    log.exception("network on_change handler failed")
