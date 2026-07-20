"""One-process-per-chunk render worker.

Invoked as: python -m app.rendering.chunk_worker <monolith.html> <out.pdf> <first> <last>

A fresh process per chunk is the reliability mechanism: Chromium render cost is
non-linear with page range and leaked memory never survives past one chunk.
The worker still loads the FULL document (pagination fidelity) and exports only
its page range.
"""
import sys
from pathlib import Path

from .engine import PlaywrightRenderEngine


def main() -> int:
    monolith, out_pdf, first, last = sys.argv[1:5]
    PlaywrightRenderEngine._print_pdf(Path(monolith), Path(out_pdf), f"{int(first)}-{int(last)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
