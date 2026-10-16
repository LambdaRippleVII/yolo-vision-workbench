"""合并模型类别信息并生成显示名称和颜色元数据。"""

from __future__ import annotations

from typing import Any

from app.model_manager.config_schema import ModelConfig

# 自动类别颜色使用的稳定调色板，保证同一类别顺序下颜色一致。
# 类别自动配色模式使用的循环调色板。
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
    """根据类别序号从固定调色板中选择颜色。

    Args:
        index: 类别在模型类别列表中的整数索引。

    Returns:
        调色板中按索引循环选择的十六进制颜色。
    """

    return AUTO_PALETTE[index % len(AUTO_PALETTE)]


def class_color(cfg: ModelConfig, class_name: str, class_index: int) -> str:
    """按模型颜色模式解析类别的显示颜色。

    Args:
        cfg: 当前模型的解析后配置。
        class_name: 模型提供的类别名称。
        class_index: 需要解析颜色的类别整数索引。

    Returns:
        当前类别最终使用的十六进制显示颜色。
    """

    if cfg.class_color_mode == "manual" and cfg.class_colors.get(class_name):
        return cfg.class_colors[class_name]
    return auto_color_for(class_index)


def _resolve_names(cfg: ModelConfig, runtime_classes: list[str] | None) -> list[str]:
    """合并模型配置和推理运行时返回的类别名称。

    Args:
        cfg: 当前模型的解析后配置。
        runtime_classes: 推理运行时返回的类别名称列表。

    Returns:
        合并、去重且保持顺序的类别名称列表。
    """
    names: list[str] = []
    if runtime_classes:
        names.extend(runtime_classes)
    if cfg.classes:
        names.extend(cfg.classes)
    # 显示名映射可能只覆盖部分类别，仅在没有其他来源时才单独使用。
    if not names and cfg.class_display:
        names.extend(cfg.class_display.keys())
    # 去重但保留首次出现顺序，确保类别编号稳定。
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return ordered


def class_entries(cfg: ModelConfig, runtime_classes: list[str] | None = None) -> list[dict[str, Any]]:
    """为每个识别类别生成名称、显示名和颜色信息。

    Args:
        cfg: 当前模型的解析后配置。
        runtime_classes: 推理运行时返回的类别名称列表。

    Returns:
        含类别编号、原名、显示名和颜色的类别条目列表。
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
    """将现有显示名与颜色配置合并到类别清单中。

    Args:
        cfg: 当前模型的解析后配置。
        class_names: 模型提供的类别名称列表。

    Returns:
        仅包含给定类别的原名到显示名映射。
    """

    out: dict[str, str] = {}
    for n in class_names:
        out[n] = cfg.display_name_of(n)
    return out
