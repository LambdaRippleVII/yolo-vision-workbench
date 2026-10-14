"""Update class display-name mapping and colors (persisted into YAML)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from app.model_manager.config_schema import ModelConfig


def update_class_display(
    model: ModelConfig,
    mapping: dict[str, str],
    *,
    class_colors: dict[str, str] | None = None,
    class_color_mode: str | None = None,
) -> dict[str, Any]:
    """Merge class_display / class_colors and write back to YAML if config_path exists."""
    merged = dict(model.class_display or {})
    for k, v in mapping.items():
        if v:
            merged[str(k)] = str(v)
        else:
            merged.pop(str(k), None)
    model.class_display = merged

    if class_colors is not None:
        colors = dict(model.class_colors or {})
        for k, v in class_colors.items():
            if v:
                colors[str(k)] = str(v)
            else:
                colors.pop(str(k), None)
        model.class_colors = colors

    if class_color_mode in ("auto", "manual"):
        model.class_color_mode = class_color_mode

    if model.config_path:
        path = Path(model.config_path)
        try:
            raw = {}
            if path.exists():
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            raw["class_display"] = merged
            raw["class_colors"] = dict(model.class_colors or {})
            raw["class_color_mode"] = model.class_color_mode
            path.write_text(
                yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            logger.info("class_display/colors updated {}", path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("write class_display failed: {}", exc)

    return {
        "class_display": merged,
        "class_colors": dict(model.class_colors or {}),
        "class_color_mode": model.class_color_mode,
    }
