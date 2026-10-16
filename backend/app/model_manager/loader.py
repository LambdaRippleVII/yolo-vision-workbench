"""扫描模型来源并管理权重、运行时和加载状态。"""

from __future__ import annotations

import threading
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from loguru import logger

from app.inference.base import BackendType
from app.model_manager.config_schema import ModelConfig
from app.model_manager.metadata import class_entries
from app.model_manager.class_persist import persist_classes
from app.model_manager.scanner import scan_models


class ModelManager:
    """扫描模型来源并协调权重检查、加载、卸载和类别信息。"""

    def __init__(self, models_dir: Path, repository_dir: Path | None = None) -> None:
        """初始化模型目录、仓库目录和运行时缓存。

        Args:
            models_dir: 本地模型及权重文件的根目录。
            repository_dir: 内置模型仓库目录。
        """

        self._models_dir = models_dir
        self._repository_dir = repository_dir or (models_dir / "repository")
        self._configs: dict[str, ModelConfig] = {}
        self._loaded: dict[str, Any] = {}
        self._lock = threading.RLock()
        self.refresh()
        self.init_class_lists()

    def refresh(self) -> list[ModelConfig]:
        """重新扫描模型目录和仓库并刷新模型配置。

        Returns:
            当前扫描到的模型配置列表。
        """

        with self._lock:
            cfgs = scan_models(self._models_dir, self._repository_dir)
            self._configs = {c.id: c for c in cfgs}
            return list(self._configs.values())

    def list_models(self) -> list[dict[str, Any]]:
        """返回本地模型和仓库模型的公开信息列表。

        Returns:
            可供前端展示的模型状态、类别和权重可用性列表。
        """

        with self._lock:
            out: list[dict[str, Any]] = []
            for cfg in self._configs.values():
                runtime = self._loaded.get(cfg.id)
                runtime_classes = runtime.get_classes() if runtime is not None else None
                # 未载入时只读取权重中的类别元数据供界面显示，不会启动推理。
                if not runtime_classes and cfg.backend in ("yolo", "mock") and not runtime:
                    runtime_classes = self._peek_classes(cfg)
                item = cfg.public_dict()
                item["loaded"] = cfg.id in self._loaded
                item["class_list"] = class_entries(cfg, runtime_classes)
                item.update(self._availability(cfg))
                out.append(item)
            return out

    def _availability(self, cfg: ModelConfig) -> dict[str, bool]:
        """根据依赖和权重文件状态计算模型的可用状态。

        Args:
            cfg: 当前模型的解析后配置。

        Returns:
            包含权重存在、是否可下载和运行时依赖是否可用的状态字典。
        """

        from app.model_manager.downloader import HUB_NAME, weight_file_available

        # 环境和权重状态仅供界面展示；查询模型列表时不会触发下载。
        if cfg.backend != "yolo":
            return {"weights_available": True, "downloadable": False, "runtime_available": True}

        try:
            runtime_available = find_spec("ultralytics") is not None and find_spec("torch") is not None
        except (ImportError, ValueError):
            runtime_available = False
        return {
            "weights_available": weight_file_available(self.resolve_weight(cfg)),
            "downloadable": cfg.id in HUB_NAME,
            "runtime_available": runtime_available,
        }

    def _peek_classes(self, cfg: ModelConfig) -> list[str] | None:
        """从运行时或配置中读取模型类别信息。

        Args:
            cfg: 当前模型的解析后配置。

        Returns:
            从运行时或配置中读取的类别名称列表；无法读取时返回 None。
        """
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
                cfg.classes = names
            return names
        except Exception as exc:  # noqa: BLE001
            logger.warning("peek classes failed {}: {}", cfg.id, exc)
            return list(cfg.classes) or None


    def init_class_lists(self) -> None:
        """为已发现模型初始化可供前端选择的类别列表。"""
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
        """按模型标识读取已扫描到的模型配置。

        Args:
            model_id: 目标模型的唯一标识。

        Returns:
            指定模型配置；模型不存在时返回 None。
        """

        with self._lock:
            return self._configs.get(model_id)

    def resolve_weight(self, cfg: ModelConfig) -> Path:
        """解析并校验模型配置指向的权重文件。

        Args:
            cfg: 当前模型的解析后配置。

        Returns:
            根据配置解析出的权重文件路径。
        """
        raw = Path(cfg.model_path)
        if raw.is_absolute():
            return raw
        if cfg.config_path:
            return (Path(cfg.config_path).parent / raw).resolve()
        return (self._models_dir / raw).resolve()

    def load(self, model_id: str, model_path: str | None = None) -> dict[str, Any]:
        """检查依赖和权重状态后显式载入模型运行时。

        Args:
            model_id: 目标模型的唯一标识。
            model_path: 模型权重文件路径。

        Returns:
            已加载模型的公开状态信息。

        Raises:
            KeyError: model_id 不存在时抛出。
            ValueError: 后端类型不受支持时抛出。
            FileNotFoundError: YOLO 权重缺失时抛出。
        """

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
            if cfg.backend == "yolo":
                from app.model_manager.downloader import HUB_NAME, weight_file_available

                # 推理请求只提示缺失项，让用户在模型管理中明确选择下载或导入。
                if not weight_file_available(weight):
                    if cfg.id in HUB_NAME:
                        raise FileNotFoundError(
                            f"模型「{cfg.name}」的权重尚未下载：{weight}。"
                            "请先在「模型管理」中点击「下载 / 重试」。"
                        )
                    raise FileNotFoundError(
                        f"模型「{cfg.name}」尚未导入权重：{weight}。"
                        "请在「模型管理」中点击「导入权重」并选择本地文件。"
                    )
            try:
                # 仅在依赖与权重均可用后才调用后端加载模型。
                runtime.load_model(weight, cfg)
            except Exception as exc:  # noqa: BLE001
                logger.error("model load failed id={} err={}", model_id, exc)
                raise

            self._loaded[model_id] = runtime
            names = runtime.get_classes()
            if names:
                setattr(cfg, "_peeked_classes", names)
                persist_classes(cfg.config_path, names)
                cfg.classes = names
            logger.info("model loaded: {} path={} classes={}", model_id, weight, len(names) if names else 0)
            return self._public_loaded(model_id)

    def load_external(self, model_path: str, *, backend: str = "yolo", name: str | None = None) -> dict[str, Any]:
        """导入并载入用户指定的外部模型权重。

        Args:
            model_path: 模型权重文件路径。
            backend: 推理后端类型或后端标识。
            name: 外部模型在界面中显示的名称。

        Returns:
            新建并载入的外部模型公开状态信息。

        Raises:
            FileNotFoundError: 外部权重文件不存在时抛出。
            ValueError: backend 不是已注册的推理后端时抛出。
        """
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
        """卸载已载入的模型并释放推理资源。

        Args:
            model_id: 目标模型的唯一标识。
        """

        with self._lock:
            runtime = self._loaded.pop(model_id, None)
            if runtime is not None:
                runtime.unload_model()
                logger.info("model unloaded: {}", model_id)

    def _public_loaded(self, model_id: str) -> dict[str, Any]:
        """生成已载入模型的前端公开状态信息。

        Args:
            model_id: 目标模型的唯一标识。

        Returns:
            包含权重、类别、运行时和可用性状态的前端公开字典。
        """

        cfg = self._configs[model_id]
        runtime = self._loaded.get(model_id)
        runtime_classes = runtime.get_classes() if runtime is not None else None
        item = cfg.public_dict()
        item["loaded"] = True
        item["class_list"] = class_entries(cfg, runtime_classes)
        item.update(self._availability(cfg))
        return item
