"""Entry point: ``python -m photo_manager`` or the installed ``photo-manager`` script.

Default invocation launches the desktop UI. Pass ``--headless`` to run the
controller without the GUI (e.g. for a server / cron-style deployment).
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from .app import AppController
from .config import Config
from .logging_config import setup_logging

log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(prog="photo-manager")
    parser.add_argument("--headless", action="store_true",
                        help="Run controller without launching the GUI")
    parser.add_argument("--upload-now", action="store_true",
                        help="Trigger an upload batch and exit (implies --headless)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    config = Config.load()

    if args.upload_now:
        return _run_once(config)

    if args.headless:
        return _run_headless(config)

    return _run_gui(config)


def _run_once(config: Config) -> int:
    controller = AppController(config)
    controller.start()
    try:
        if config.oauth_client_secret_path:
            controller.authenticate()
        result = controller.upload_now()
        log.info("upload result: %s", result)
        return 0
    finally:
        controller.stop()


def _run_headless(config: Config) -> int:
    controller = AppController(config)
    controller.start()
    if config.oauth_client_secret_path:
        try:
            controller.authenticate()
        except Exception:
            log.exception("authentication failed; running without uploads")

    stop = False

    def handler(signum, _frame):
        nonlocal stop
        log.info("signal %s received; shutting down", signum)
        stop = True

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    try:
        while not stop:
            time.sleep(1)
    finally:
        controller.stop()
    return 0


def _run_gui(config: Config) -> int:
    try:
        from .ui.main_window import run_gui
    except ImportError as e:
        log.error("PyQt6 not installed (%s); falling back to headless. "
                  "Install with: pip install PyQt6", e)
        return _run_headless(config)
    return run_gui(config)


if __name__ == "__main__":
    sys.exit(main())
