"""封装兼容 Windows 中文路径的图像和视频读写。"""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path: str | Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """通过 Unicode 路径读取图像，失败时返回 None。

    Args:
        path: 待读取、写入或检查的文件系统路径。
        flags: OpenCV 图像读取标志，例如 ``cv2.IMREAD_COLOR``。

    Returns:
        解码后的图像数组；文件不存在或无法解码时返回 None。
    """
    # NumPy 的文件读取支持 Windows 中文路径，再把字节缓冲区交给 OpenCV 解码。
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
    """通过 Unicode 路径保存图像并返回写入是否成功。

    Args:
        path: 待读取、写入或检查的文件系统路径。
        image: 待处理的图像数据。

    Returns:
        图像是否成功写入目标路径。
    """

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
    """获取 Windows 短路径以兼容不支持中文路径的解码器。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        纯 ASCII 的 Windows 短路径；不适用或转换失败时返回 None。
    """
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
    """打开视频文件，并在 Windows 下尝试短路径兼容回退。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        已打开的视频捕获对象；调用方负责检查 isOpened 并释放资源。
    """
    # 依次尝试原始路径、规范化路径和 Windows 短路径，兼容不同 OpenCV 构建。
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
        # 释放失败的句柄，避免连续尝试时占用视频文件资源。
        if capture is not None:
            capture.release()
        capture = cv2.VideoCapture(candidate)
        if capture.isOpened():
            return capture

    if capture is not None:
        return capture
    return cv2.VideoCapture(str(original))


def video_open_error_message(path: str | Path) -> str:
    """生成带有可操作线索的视频打开错误提示。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        包含文件路径、权限和编码建议的中文错误信息。
    """

    message = f"OpenCV 无法打开视频：{path}。请检查文件权限、完整性和编码格式。"
    if os.name == "nt" and not str(path).isascii():
        message += "如果路径含中文或特殊字符，请将视频文件名或所在目录改为英文/数字后重试。"
    return message
