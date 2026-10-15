"""HTTP helpers to stream local media to the renderer (file:// often fails for video)."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote


def guess_media_type(path: Path) -> str:
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype or "application/octet-stream"


def resolve_media_path(raw: str, allowed_roots: list[Path]) -> Path | None:
    """Only serve files under allowed roots (project / models / temp)."""
    p = Path(unquote(str(raw))).expanduser()
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
    # also allow absolute files on same drive for user media
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
