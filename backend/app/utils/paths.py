"""Path helpers. Always use these instead of hardcoding absolute paths."""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig


def resolve_under_root(cfg: AppConfig, maybe_relative: str | Path) -> Path:
    """Resolve a path that may be relative to the project root."""
    p = Path(maybe_relative)
    if p.is_absolute():
        return p.resolve()
    return (cfg.root / p).resolve()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
