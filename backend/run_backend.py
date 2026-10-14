"""Bootstrap launcher for packaged app (embeddable Python ignores PYTHONPATH)."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # backend package dir is parent of this file (backend/run_backend.py)
    backend_dir = Path(__file__).resolve().parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    import runpy

    runpy.run_module("app.main", run_name="__main__")


if __name__ == "__main__":
    main()
