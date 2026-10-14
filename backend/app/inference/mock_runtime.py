"""Mock runtime for UI development without ultralytics/weights.

Enabled when model YAML has backend: mock, or as fallback demo backend.
"""

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
    backend_type = BackendType.YOLO  # registry keyed by config.backend string via factory

    def __init__(self) -> None:
        super().__init__()
        self._config: Any = None
        self._classes: list[str] = []
        self._model_id = "mock"

    def load_model(self, model_path: Path, config: Any) -> None:
        self._config = config
        self._model_id = getattr(config, "id", "mock")
        self._classes = list(getattr(config, "classes", []) or ["object"])
        self.model_task = ModelTaskType.DETECT
        self._loaded = True
        logger.info("MockRuntime loaded model_id={}", self._model_id)

    def unload_model(self) -> None:
        self._loaded = False

    def get_classes(self) -> list[str]:
        return list(self._classes)

    def predict(self, image: np.ndarray) -> list[ResultObject]:
        if not self._loaded:
            raise RuntimeError("mock runtime not loaded")
        h, w = image.shape[:2]
        time.sleep(0.05)  # simulate latency
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
