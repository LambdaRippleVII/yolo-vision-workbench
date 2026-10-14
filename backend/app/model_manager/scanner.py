"""Scan models directories for YAML configs."""

from __future__ import annotations

from pathlib import Path

import yaml
from loguru import logger

from app.model_manager.config_schema import ModelConfig


def _load_one(path: Path, source: str) -> ModelConfig | None:
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
    """Collect ModelConfig from local examples/user dirs and optional repository packages."""
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
