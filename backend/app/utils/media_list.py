"""扫描目录并列出受支持的图像文件。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# 媒体扫描器认可的图像文件扩展名集合。
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def list_folder_images(folder: str | Path, *, recursive: bool = False) -> list[dict[str, Any]]:
    """扫描目录并生成符合扩展名规则的图片清单。

    Args:
        folder: 要扫描图片的目录路径。
        recursive: 是否递归扫描子目录。

    Returns:
        按名称排序的图片路径和文件名列表。

    Raises:
        NotADirectoryError: folder 不是已存在的目录时抛出。
    """

    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(f"not a folder: {folder}")
    files: list[Path] = []
    if recursive:
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                files.append(p)
    else:
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                files.append(p)
    files = sorted(files, key=lambda p: p.name.lower())
    return [
        {
            "path": str(p),
            "name": p.name,
            "size": p.stat().st_size,
        }
        for p in files
    ]
