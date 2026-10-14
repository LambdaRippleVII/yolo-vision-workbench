"""Create backend virtualenv and install requirements.

Usage:
    python setup_env.py
    python setup_env.py --requirements base yolo

Prefers local wheels/ directory when present (offline-friendly).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
WHEELS = ROOT / "wheels"
REQ_DIR = ROOT / "requirements"


def python_in_venv() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup YOLO Vision Workbench backend env")
    parser.add_argument(
        "--requirements",
        nargs="+",
        default=["base"],
        help="requirement file names without .txt (default: base)",
    )
    args = parser.parse_args()

    if not VENV.exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    py = str(python_in_venv())
    run([py, "-m", "pip", "install", "--upgrade", "pip"])

    for name in args.requirements:
        req = REQ_DIR / f"{name}.txt"
        if not req.exists():
            print(f"missing requirements file: {req}")
            return 1
        cmd = [py, "-m", "pip", "install", "-r", str(req)]
        if WHEELS.exists() and any(WHEELS.iterdir()):
            cmd.extend(["--no-index", "--find-links", str(WHEELS)])
            print("using local wheels (no-index)")
        # Try wheels first; if it fails (missing pkgs), fall back to network.
        try:
            run(cmd)
        except subprocess.CalledProcessError:
            if "--no-index" in cmd:
                print("local wheels incomplete, falling back to network install")
                run([py, "-m", "pip", "install", "-r", str(req)])
            else:
                return 1

    print("backend env ready:", py)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
