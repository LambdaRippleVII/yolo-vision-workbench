"""封装 Ultralytics YOLO 模型的加载、推理和释放。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from app.inference.base import (
    BackendType,
    BaseRuntime,
    Geometry,
    GeometryType,
    ModelTaskType,
    ResultObject,
)


class ModelLoadError(RuntimeError):
    """表示模型权重或推理依赖无法正常加载。"""

    pass


class YOLORuntime(BaseRuntime):
    """把 Ultralytics YOLO 模型适配到统一推理接口。"""

    backend_type = BackendType.YOLO

    def __init__(self) -> None:
        """初始化YOLORuntime实例并准备运行所需状态。"""

        super().__init__()
        self._model: Any = None
        self._config: Any = None
        self._classes: list[str] = []
        self._model_id: str = ""

    def load_model(self, model_path: Path, config: Any) -> None:
        """根据权重路径和模型配置初始化推理后端。

        Args:
            model_path: 模型权重文件路径。
            config: 当前操作使用的应用或模型配置。

        Raises:
            ModelLoadError: 权重文件不存在、依赖缺失或模型加载失败时抛出。
        """

        self._config = config
        self._model_id = getattr(config, "id", "model")
        task = getattr(config, "task", "detect")
        try:
            self.model_task = ModelTaskType(task)
        except ValueError:
            self.model_task = ModelTaskType.DETECT

        if not Path(model_path).exists():
            raise ModelLoadError(f"weights not found: {model_path}")

        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise ModelLoadError(
                "YOLO 推理组件（ultralytics/torch）尚未安装。请回到首次启动初始化提示重试；"
                "开发环境可运行：uv pip install -r requirements/yolo.txt"
            ) from exc

        try:
            self._model = YOLO(str(model_path))
        except Exception as exc:  # noqa: BLE001
            raise ModelLoadError(f"failed to load weights: {exc}") from exc

        names = getattr(self._model, "names", None)
        if isinstance(names, dict):
            self._classes = [str(names[k]) for k in sorted(names.keys())]
        elif isinstance(names, list):
            self._classes = [str(n) for n in names]
        else:
            self._classes = list(getattr(config, "classes", []) or [])

        self._loaded = True
        logger.info("YOLORuntime loaded model_id={} path={}", self._model_id, model_path)

    def unload_model(self) -> None:
        """释放当前运行时持有的模型和推理资源。"""

        self._model = None
        self._loaded = False
        logger.info("YOLORuntime unloaded model_id={}", self._model_id)

    def get_classes(self) -> list[str]:
        """返回模型运行时识别到的类别名称列表。

        Returns:
            当前模型的类别名称列表。
        """

        return list(self._classes)

    def predict(self, image: np.ndarray) -> list[ResultObject]:
        """对输入图像执行推理并转换为统一结果对象。

        Args:
            image: 待处理的图像数据。

        Returns:
            当前图像中检测到的统一结果对象列表。

        Raises:
            RuntimeError: 尚未加载模型或 Ultralytics 推理调用失败时抛出。
        """

        if not self._loaded or self._model is None:
            raise RuntimeError("runtime not loaded")

        conf = float(getattr(self._config, "conf", 0.45))
        iou = float(getattr(self._config, "iou", 0.5))
        # 封装 Ultralytics 调用，上层只接收统一的 ResultObject 列表。
        results = self._model.predict(image, conf=conf, iou=iou, verbose=False)

        objects: list[ResultObject] = []
        obj_id = 1
        display_map = getattr(self._config, "class_display", {}) or {}

        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].tolist()
                cls_id = int(box.cls[0].item()) if hasattr(box.cls[0], "item") else int(box.cls[0])
                conf_v = float(box.conf[0].item()) if hasattr(box.conf[0], "item") else float(box.conf[0])
                class_name = self._classes[cls_id] if 0 <= cls_id < len(self._classes) else str(cls_id)
                from app.model_manager.metadata import class_color

                color = class_color(self._config, class_name, cls_id) if self._config else "#2F6FED"
                objects.append(
                    ResultObject(
                        id=obj_id,
                        model_id=self._model_id,
                        class_id=cls_id,
                        class_name=class_name,
                        display_name=display_map.get(class_name, class_name),
                        confidence=conf_v,
                        geometry=Geometry(type=GeometryType.BBOX, bbox=(xyxy[0], xyxy[1], xyxy[2], xyxy[3])),
                        style={"color": color, "line_width": getattr(getattr(self._config, "render", None), "line_width", 2)},
                    )
                )
                obj_id += 1
        return objects
