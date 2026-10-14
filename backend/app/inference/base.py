"""Inference runtime contracts (P1 skeleton).

Full Geometry multi-type support is documented in IMPLEMENTATION_DESIGN.
Predict implementations live in backend-specific runtimes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class BackendType(str, Enum):
    YOLO = "yolo"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    RKNN = "rknn"
    MOCK = "mock"


class ModelTaskType(str, Enum):
    DETECT = "detect"
    SEGMENT = "segment"
    POSE = "pose"
    OCR = "ocr"
    TRACK = "track"
    CUSTOM = "custom"


class GeometryType(str, Enum):
    BBOX = "bbox"
    MASK = "mask"
    KEYPOINTS = "keypoints"
    POLYGON = "polygon"
    TEXT = "text"


@dataclass
class Geometry:
    type: GeometryType = GeometryType.BBOX
    bbox: tuple[float, float, float, float] | None = None
    mask_ref: str | None = None
    points: list[tuple[float, float]] | None = None
    keypoints: list[dict[str, Any]] | None = None
    text: str | None = None
    text_conf: float | None = None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"type": self.type.value}
        if self.bbox is not None:
            data["bbox"] = list(self.bbox)
        if self.mask_ref is not None:
            data["mask_ref"] = self.mask_ref
        if self.points is not None:
            data["points"] = [list(p) for p in self.points]
        if self.keypoints is not None:
            data["keypoints"] = self.keypoints
        if self.text is not None:
            data["text"] = self.text
        if self.text_conf is not None:
            data["text_conf"] = self.text_conf
        return data


@dataclass
class ResultObject:
    id: int
    model_id: str
    class_id: int
    class_name: str
    display_name: str
    confidence: float
    geometry: Geometry
    track_id: int | None = None
    visible: bool = True
    style: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "geom_type": self.geometry.type.value,
            "geom": self.geometry.to_json(),
            "track_id": self.track_id,
            "visible": self.visible,
            "style": self.style,
        }


@dataclass
class FrameResult:
    frame_id: int
    media_ref: str
    objects: list[ResultObject]
    meta: dict[str, Any] = field(default_factory=dict)


class BaseRuntime(ABC):
    """Unified inference backend interface. Never call model.predict() above this layer."""

    backend_type: BackendType
    model_task: ModelTaskType = ModelTaskType.DETECT

    def __init__(self) -> None:
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @abstractmethod
    def load_model(self, model_path: Path, config: Any) -> None: ...

    @abstractmethod
    def unload_model(self) -> None: ...

    @abstractmethod
    def predict(self, image: np.ndarray) -> list[ResultObject]: ...

    @abstractmethod
    def get_classes(self) -> list[str]: ...
