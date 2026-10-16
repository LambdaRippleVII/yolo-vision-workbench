"""将运行时读取到的类别列表安全写回模型配置。"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger


def persist_classes(cfg_path: str | None, classes: list[str], *, limit: int = 2000) -> bool:
    """将模型类别列表写入配置文件并限制保存条目数量。

    Args:
        cfg_path: 要写入类别列表的模型 YAML 配置路径。
        classes: 模型类别名称列表。
        limit: 本次查询或保存允许处理的最大条目数。

    Returns:
        是否成功写入类别列表。
    """
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
