"""扫描模型目录并解析模型配置文件。"""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from app.model_manager.config_schema import ModelConfig


def _load_one(path: Path, source: str) -> ModelConfig | None:
    """读取单个模型 YAML 配置并处理无效配置。

    Args:
        path: 待读取、写入或检查的文件系统路径。
        source: 模型或数据的来源标识。

    Returns:
        解析后的模型配置；配置无效时返回 None。
    """

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            logger.warning("model config ignored (not a mapping): {}", path)
            return None
        if "id" not in raw:
            raw["id"] = path.stem
        cfg = ModelConfig.model_validate(raw)
        cfg.config_path = str(path)
        cfg.source_dir = source
        return cfg
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to parse model config {}: {}", path, exc)
        return None


def scan_models(models_dir: Path, repository_dir: Path | None = None) -> list[ModelConfig]:
    """扫描用户模型目录和内置仓库中的模型配置。

    Args:
        models_dir: 本地模型及权重文件的根目录。
        repository_dir: 内置模型仓库目录。

    Returns:
        按来源去重后的模型配置列表。
    """
    found: list[ModelConfig] = []
    seen_ids: set[str] = set()

    if models_dir.exists():
        for path in sorted(models_dir.rglob("*.yaml")):
            if repository_dir and repository_dir in path.parents:
                continue
            cfg = _load_one(path, source="local")
            if cfg and cfg.id not in seen_ids:
                seen_ids.add(cfg.id)
                found.append(cfg)

    if repository_dir and repository_dir.exists():
        catalog = repository_dir / "catalog.yaml"
        if catalog.exists():
            logger.info("repository catalog present: {}", catalog)
        for path in sorted(repository_dir.rglob("*.yaml")):
            if path.name == "catalog.yaml":
                continue
            cfg = _load_one(path, source="repository")
            if cfg and cfg.id not in seen_ids:
                seen_ids.add(cfg.id)
                found.append(cfg)

    logger.info("scanned {} model configs", len(found))
    return found
