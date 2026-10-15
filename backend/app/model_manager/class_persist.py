"""Persist class names discovered from weights back to model YAML."""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger


def persist_classes(cfg_path: str | None, classes: list[str], *, limit: int = 2000) -> bool:
    """Write `classes:` into model YAML so UI lists all names without reloading."""
    if not cfg_path or not classes:
        return False
    path = Path(cfg_path)
    if not path.exists() or path.suffix.lower() not in (".yaml", ".yml"):
        return False
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            return False
        names = [str(n) for n in classes][:limit]
        if raw.get("classes") == names:
            return False
        raw["classes"] = names
        path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        logger.info("persisted {} classes -> {}", len(names), path)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("persist classes failed {}: {}", cfg_path, exc)
        return False
