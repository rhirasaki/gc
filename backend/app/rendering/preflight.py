"""Pre-flight checks before heavy render sessions (§12 / reference §4.4).

Never assume prior container configuration persisted: check swap and disk at
the start of every heavy render and fail fast with an actionable error rather
than hanging inscrutably mid-render.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import settings


class PreflightError(RuntimeError):
    """Raised when the environment cannot safely run a heavy render."""


@dataclass
class PreflightReport:
    swap_active: bool
    swap_total_mb: float
    free_disk_gb: float
    ok: bool
    messages: list[str]


def read_swap_mb(proc_swaps: str | Path = "/proc/swaps") -> float:
    """Total active swap in MB, 0.0 if none or the file is unreadable."""
    try:
        lines = Path(proc_swaps).read_text().strip().splitlines()
    except OSError:
        return 0.0
    total_kb = 0
    for line in lines[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 3:
            try:
                total_kb += int(parts[2])
            except ValueError:
                continue
    return total_kb / 1024


def free_disk_gb(path: str | Path = ".") -> float:
    p = Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / 1024**3


def run_preflight(
    workdir: str | Path,
    *,
    heavy: bool,
    min_free_gb: float | None = None,
    require_swap: bool | None = None,
) -> PreflightReport:
    """Check the environment. Raises PreflightError for a heavy render that
    can't proceed; light renders only warn."""
    min_free_gb = settings.min_free_disk_gb if min_free_gb is None else min_free_gb
    require_swap = settings.require_swap if require_swap is None else require_swap

    swap_mb = read_swap_mb()
    disk_gb = free_disk_gb(workdir)
    messages: list[str] = []
    ok = True

    if disk_gb < min_free_gb:
        ok = False
        messages.append(
            f"Only {disk_gb:.1f}GB free disk at {workdir} (need {min_free_gb}GB). "
            "Run artifact cleanup or free space before rendering."
        )
    if heavy and require_swap and swap_mb <= 0:
        ok = False
        messages.append(
            "No active swap (/proc/swaps is empty). Heavy renders on this machine "
            "have OOM-killed Chromium without swap. Enable swap or lower the "
            "chunk threshold, then retry."
        )

    report = PreflightReport(
        swap_active=swap_mb > 0, swap_total_mb=swap_mb, free_disk_gb=disk_gb, ok=ok, messages=messages
    )
    if heavy and not ok:
        raise PreflightError(" | ".join(messages))
    return report
