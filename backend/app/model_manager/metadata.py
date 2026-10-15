"""Model metadata helpers: class lists and display-name mapping."""

from __future__ import annotations

from typing import Any

from app.model_manager.config_schema import ModelConfig

# stable palette for auto class colors
AUTO_PALETTE = [
    "#2F6FED",
    "#E85D4C",
    "#1F9D66",
    "#C47B12",
    "#7C4DFF",
    "#0E7C86",
    "#D64545",
    "#5B9CFF",
    "#B45F06",
    "#2A7FA8",
]


def auto_color_for(index: int) -> str:
    return AUTO_PALETTE[index % len(AUTO_PALETTE)]


def class_color(cfg: ModelConfig, class_name: str, class_index: int) -> str:
    if cfg.class_color_mode == "manual" and cfg.class_colors.get(class_name):
        return cfg.class_colors[class_name]
    return auto_color_for(class_index)


def _resolve_names(cfg: ModelConfig, runtime_classes: list[str] | None) -> list[str]:
    """Full class name list: runtime > YAML classes > display-map keys."""
    names: list[str] = []
    if runtime_classes:
        names.extend(runtime_classes)
    if cfg.classes:
        names.extend(cfg.classes)
    # display map only covers mapped subset; do not use as sole source unless nothing else
    if not names and cfg.class_display:
        names.extend(cfg.class_display.keys())
    # unique, keep order
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def class_entries(cfg: ModelConfig, runtime_classes: list[str] | None = None) -> list[dict[str, Any]]:
    """Build UI-facing class list.

    Always expose every known class_name.
    display_name = class_display[name] if mapped else name (原名原样显示).
    """
    names = _resolve_names(cfg, runtime_classes)
    entries: list[dict[str, Any]] = []
    for idx, name in enumerate(names):
        entries.append(
            {
                "class_id": idx,
                "class_name": name,
                "display_name": cfg.display_name_of(name),
                "color": class_color(cfg, name, idx),
            }
        )
    return entries


def merge_display_map(cfg: ModelConfig, class_names: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for n in class_names:
        out[n] = cfg.display_name_of(n)
    return out
