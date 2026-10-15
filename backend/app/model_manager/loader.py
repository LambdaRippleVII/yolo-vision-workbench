"""Model load/unload cache. Configs scanned once; runtimes created on demand."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from loguru import logger

from app.inference.base import BackendType
from app.model_manager.config_schema import ModelConfig
from app.model_manager.metadata import class_entries
from app.model_manager.class_persist import persist_classes
from app.model_manager.scanner import scan_models


class ModelManager:
    def __init__(self, models_dir: Path, repository_dir: Path | None = None) -> None:
        self._models_dir = models_dir
        self._repository_dir = repository_dir or (models_dir / "repository")
        self._configs: dict[str, ModelConfig] = {}
        self._loaded: dict[str, Any] = {}
        self._lock = threading.RLock()
        self.refresh()
        self.init_class_lists()

    def refresh(self) -> list[ModelConfig]:
        with self._lock:
            cfgs = scan_models(self._models_dir, self._repository_dir)
            self._configs = {c.id: c for c in cfgs}
            return list(self._configs.values())

    def list_models(self) -> list[dict[str, Any]]:
        with self._lock:
            out: list[dict[str, Any]] = []
            for cfg in self._configs.values():
                runtime = self._loaded.get(cfg.id)
                runtime_classes = runtime.get_classes() if runtime is not None else None
                # For unloaded YOLO models, peek names from weights so UI can show full class list
                if not runtime_classes and cfg.backend in ("yolo", "mock") and not runtime:
                    runtime_classes = self._peek_classes(cfg)
                item = cfg.public_dict()
                item["loaded"] = cfg.id in self._loaded
                item["class_list"] = class_entries(cfg, runtime_classes)
                out.append(item)
            return out

    def _peek_classes(self, cfg: ModelConfig) -> list[str] | None:
        """Read class names without keeping a runtime instance (cache on config)."""
        cached = getattr(cfg, "_peeked_classes", None)
        if cached:
            return cached
        try:
            if cfg.backend == "mock":
                names = list(cfg.classes) or list(cfg.class_display.keys())
                setattr(cfg, "_peeked_classes", names)
                return names
            from ultralytics import YOLO  # type: ignore

            weight = self.resolve_weight(cfg)
            if not weight.exists():
                return list(cfg.classes) or None
            model = YOLO(str(weight))
            names_attr = getattr(model, "names", None)
            if isinstance(names_attr, dict):
                names = [str(names_attr[k]) for k in sorted(names_attr.keys())]
            elif isinstance(names_attr, list):
                names = [str(n) for n in names_attr]
            else:
                names = list(cfg.classes)
            setattr(cfg, "_peeked_classes", names)
            if names:
                persist_classes(cfg.config_path, names)
                if not cfg.classes:
                    cfg.classes = names
            return names
        except Exception as exc:  # noqa: BLE001
            logger.warning("peek classes failed {}: {}", cfg.id, exc)
            return list(cfg.classes) or None


    def init_class_lists(self) -> None:
        """First-time init: extract class names from local weights and cache in YAML."""
        with self._lock:
            for cfg in self._configs.values():
                if getattr(cfg, '_peeked_classes', None):
                    continue
                if cfg.backend == 'mock':
                    continue
                if cfg.classes:
                    continue
                self._peek_classes(cfg)

    def get_config(self, model_id: str) -> ModelConfig | None:
        with self._lock:
            return self._configs.get(model_id)

    def resolve_weight(self, cfg: ModelConfig) -> Path:
        """Resolve model_path relative to the YAML file directory."""
        raw = Path(cfg.model_path)
        if raw.is_absolute():
            return raw
        if cfg.config_path:
            return (Path(cfg.config_path).parent / raw).resolve()
        return (self._models_dir / raw).resolve()

    def load(self, model_id: str, model_path: str | None = None) -> dict[str, Any]:
        with self._lock:
            if model_id in self._loaded:
                logger.info("model already loaded: {}", model_id)
                return self._public_loaded(model_id)

            cfg = self._configs.get(model_id)
            if cfg is None:
                raise KeyError(f"model not found: {model_id}")

            from app.runtime.registry import registry

            try:
                backend_type = BackendType(cfg.backend)
            except ValueError as exc:
                raise ValueError(f"unsupported backend: {cfg.backend}") from exc

            runtime = registry.create(backend_type)
            weight = Path(model_path).resolve() if model_path else self.resolve_weight(cfg)
            if not weight.exists() and cfg.backend == "yolo":
                from app.model_manager.downloader import download_weight, _default_filename

                try:
                    weight = download_weight(
                        cfg.id,
                        self._models_dir / "examples" / "weights" / _default_filename(cfg.id),
                    )
                except Exception as dl_exc:  # noqa: BLE001
                    raise FileNotFoundError(
                        f"模型权重不存在：{weight}。请点「下载内置模型」，或手动放入 weights 目录。详情：{dl_exc}"
                    ) from dl_exc
            try:
                runtime.load_model(weight, cfg)
            except Exception as exc:  # noqa: BLE001
                logger.error("model load failed id={} err={}", model_id, exc)
                raise

            self._loaded[model_id] = runtime
            names = runtime.get_classes()
            if names:
                setattr(cfg, "_peeked_classes", names)
                persist_classes(cfg.config_path, names)
                if not cfg.classes:
                    cfg.classes = names
            logger.info("model loaded: {} path={} classes={}", model_id, weight, len(names) if names else 0)
            return self._public_loaded(model_id)

    def load_external(self, model_path: str, *, backend: str = "yolo", name: str | None = None) -> dict[str, Any]:
        """Temporarily load a local weight file without a pre-registered YAML."""
        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"model file not found: {path}")
        model_id = f"ext_{path.stem}"
        try:
            backend_type = BackendType(backend)
        except ValueError as exc:
            raise ValueError(f"unsupported backend: {backend}") from exc

        from app.inference.base import ModelTaskType  # noqa: F401
        from app.runtime.registry import registry

        cfg = ModelConfig(
            id=model_id,
            name=name or path.name,
            backend=backend,
            model_path=str(path),
            task="detect",
            config_path=str(path),
            source_dir="user",
        )
        with self._lock:
            self._configs[model_id] = cfg
            runtime = registry.create(backend_type)
            runtime.load_model(path, cfg)
            self._loaded[model_id] = runtime
            names = runtime.get_classes()
            if names:
                cfg.classes = names
                setattr(cfg, "_peeked_classes", names)
            logger.info("external model loaded {} classes={}", model_id, len(names) if names else 0)
            return self._public_loaded(model_id)

    def unload(self, model_id: str) -> None:
        with self._lock:
            runtime = self._loaded.pop(model_id, None)
            if runtime is not None:
                runtime.unload_model()
                logger.info("model unloaded: {}", model_id)

    def _public_loaded(self, model_id: str) -> dict[str, Any]:
        cfg = self._configs[model_id]
        runtime = self._loaded.get(model_id)
        runtime_classes = runtime.get_classes() if runtime is not None else None
        item = cfg.public_dict()
        item["loaded"] = True
        item["class_list"] = class_entries(cfg, runtime_classes)
        return item
