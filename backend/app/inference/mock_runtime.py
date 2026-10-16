"""提供用于界面联调和流程验证的模拟推理后端。"""

from __future__ import annotations

import time
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


class MockRuntime(BaseRuntime):
    """以可重复的模拟结果实现通用推理后端接口。"""

    # 工厂通过配置中的 backend 字符串查找此运行时实现。
    backend_type = BackendType.YOLO

    def __init__(self) -> None:
        """初始化MockRuntime实例并准备运行所需状态。"""

        super().__init__()
        self._config: Any = None
        self._classes: list[str] = []
        self._model_id = "mock"

    def load_model(self, model_path: Path, config: Any) -> None:
        """根据权重路径和模型配置初始化推理后端。

        Args:
            model_path: 模型权重文件路径。
            config: 当前操作使用的应用或模型配置。
        """

        self._config = config
        self._model_id = getattr(config, "id", "mock")
        self._classes = list(getattr(config, "classes", []) or ["object"])
        self.model_task = ModelTaskType.DETECT
        self._loaded = True
        logger.info("MockRuntime loaded model_id={}", self._model_id)

    def unload_model(self) -> None:
        """释放当前运行时持有的模型和推理资源。"""

        self._loaded = False

    def get_classes(self) -> list[str]:
        """返回模型运行时识别到的类别名称列表。

        Returns:
            模拟模型的类别名称列表。
        """

        return list(self._classes)

    def predict(self, image: np.ndarray) -> list[ResultObject]:
        """对输入图像执行推理并转换为统一结果对象。

        Args:
            image: 待处理的图像数据。

        Returns:
            根据输入图像尺寸生成的模拟检测对象列表。

        Raises:
            RuntimeError: 模拟运行时尚未加载时抛出。
        """

        if not self._loaded:
            raise RuntimeError("mock runtime not loaded")
        h, w = image.shape[:2]
        # 模拟真实推理的最小耗时，便于开发环境观察进度事件。
        time.sleep(0.05)
        display_map = getattr(self._config, "class_display", {}) or {}
        color = getattr(getattr(self._config, "render", None), "color", "#2F6FED")
        line_w = getattr(getattr(self._config, "render", None), "line_width", 2)

        objects: list[ResultObject] = []
        from app.model_manager.metadata import class_color

        for i, name in enumerate(self._classes):
            x1 = w * (0.12 + 0.18 * i)
            y1 = h * (0.18 + 0.05 * i)
            x2 = x1 + w * 0.28
            y2 = y1 + h * 0.42
            color = class_color(self._config, name, i) if self._config else color
            objects.append(
                ResultObject(
                    id=i + 1,
                    model_id=self._model_id,
                    class_id=i,
                    class_name=name,
                    display_name=display_map.get(name, name),
                    confidence=round(0.92 - 0.07 * i, 3),
                    geometry=Geometry(type=GeometryType.BBOX, bbox=(x1, y1, x2, y2)),
                    style={"color": color, "line_width": line_w},
                )
            )
        return objects
