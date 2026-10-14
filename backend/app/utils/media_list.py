"""List images in a folder for the album UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}


def list_folder_images(folder: str | Path, *, recursive: bool = False) -> list[dict[str, Any]]:
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
