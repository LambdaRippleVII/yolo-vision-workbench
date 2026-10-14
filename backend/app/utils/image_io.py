"""Image/video IO helpers — Windows-safe for non-ASCII paths."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """cv2.imread fails on Windows with non-ASCII paths; use fromfile+imdecode."""
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = np.fromfile(str(p), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, flags)
    except Exception:  # noqa: BLE001
        return None


def imwrite_unicode(path: str | Path, image: np.ndarray) -> bool:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ext = p.suffix or ".jpg"
    ok, buf = cv2.imencode(ext, image)
    if not ok:
        return False
    try:
        buf.tofile(str(p))
        return True
    except Exception:  # noqa: BLE001
        return False


def open_video_capture(path: str | Path) -> cv2.VideoCapture:
    """Open video; retry with backslashes normalized for Windows unicode paths."""
    p = Path(path)
    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        cap = cv2.VideoCapture(str(p.resolve()))
    return cap
