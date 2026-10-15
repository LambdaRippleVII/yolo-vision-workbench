"""Image/video IO helpers — Windows-safe for non-ASCII paths."""

from __future__ import annotations

import os
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


def _windows_short_path(path: Path) -> str | None:
    """Return an ASCII 8.3 alias when Windows has one for every path segment."""
    path_text = str(path)
    if os.name != "nt" or path_text.isascii():
        return None

    try:
        import ctypes

        get_short_path_name = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        get_short_path_name.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        get_short_path_name.restype = ctypes.c_uint32
        buffer = ctypes.create_unicode_buffer(32_768)
        length = get_short_path_name(str(path), buffer, len(buffer))
        if not length or length >= len(buffer):
            return None
        short_path = buffer.value
        if short_path == path_text or not short_path.isascii():
            return None
        return short_path
    except (AttributeError, OSError):
        return None


def open_video_capture(path: str | Path) -> cv2.VideoCapture:
    """Open video, retrying with a Windows short path for Unicode filenames."""
    original = Path(path).expanduser()
    candidates = [str(original)]
    try:
        resolved = original.resolve()
    except (OSError, RuntimeError):
        resolved = original
    if str(resolved) not in candidates:
        candidates.append(str(resolved))

    short_path = _windows_short_path(resolved)
    if short_path and short_path not in candidates:
        candidates.append(short_path)

    capture: cv2.VideoCapture | None = None
    for candidate in candidates:
        if capture is not None:
            capture.release()
        capture = cv2.VideoCapture(candidate)
        if capture.isOpened():
            return capture

    if capture is not None:
        return capture
    return cv2.VideoCapture(str(original))


def video_open_error_message(path: str | Path) -> str:
    message = f"OpenCV 无法打开视频：{path}。请检查文件权限、完整性和编码格式。"
    if os.name == "nt" and not str(path).isascii():
        message += "如果路径含中文或特殊字符，请将视频文件名或所在目录改为英文/数字后重试。"
    return message
