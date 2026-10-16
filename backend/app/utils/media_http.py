"""校验媒体访问路径并推断 HTTP 内容类型。"""

from __future__ import annotations

import mimetypes
from pathlib import Path


def guess_media_type(path: Path) -> str:
    """根据文件扩展名推断 HTTP 响应的媒体类型。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        MIME 类型字符串；无法识别时返回 application/octet-stream。
    """

    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"


def resolve_media_path(raw: str, allowed_roots: list[Path]) -> Path | None:
    """只在允许根目录内解析并返回存在的媒体文件。

    Args:
        raw: 尚未解析的输入消息或原始值。
        allowed_roots: 允许解析媒体文件的根目录列表。

    Returns:
        允许访问且存在的媒体文件路径；校验失败时返回 None。
    """
    # FastAPI 已经解码查询参数；再次解码会破坏包含字面量百分号序列（如 "%20"）的文件名。
    p = Path(str(raw)).expanduser()
    try:
        p = p.resolve()
    except Exception:  # noqa: BLE001
        return None
    if not p.is_file():
        return None
    for root in allowed_roots:
        try:
            p.relative_to(root.resolve())
            return p
        except ValueError:
            continue
    # 同时允许同一磁盘上的用户媒体绝对路径。
    if p.suffix.lower() in {
        ".mp4",
        ".m4v",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".flv",
        ".3gp",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        return p
    return None
