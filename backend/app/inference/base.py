"""定义推理后端、几何数据和检测结果的通用契约。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np


class BackendType(str, Enum):
    """列出应用支持的推理后端标识。"""

    YOLO = "yolo"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    RKNN = "rknn"
    MOCK = "mock"


class ModelTaskType(str, Enum):
    """列出模型可执行的视觉任务类型。"""

    DETECT = "detect"
    SEGMENT = "segment"
    POSE = "pose"
    OCR = "ocr"
    TRACK = "track"
    CUSTOM = "custom"


class GeometryType(str, Enum):
    """列出检测结果支持的几何数据类型。"""

    BBOX = "bbox"
    MASK = "mask"
    KEYPOINTS = "keypoints"
    POLYGON = "polygon"
    TEXT = "text"


@dataclass
class Geometry:
    """统一保存检测框、掩码、关键点和文本等几何信息。"""

    type: GeometryType = GeometryType.BBOX
    bbox: tuple[float, float, float, float] | None = None
    mask_ref: str | None = None
    points: list[tuple[float, float]] | None = None
    keypoints: list[dict[str, Any]] | None = None
    text: str | None = None
    text_conf: float | None = None

    def to_json(self) -> dict[str, Any]:
        """把几何数据转换为仅包含已设置字段的字典。

        Returns:
            仅包含已设置几何字段的可序列化字典。
        """

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
    """保存单个检测对象及其类别、置信度、几何和样式。"""

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
        """把检测对象转换为前后端协议使用的字典。

        Returns:
            符合前后端协议的检测对象字典。
        """

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
    """保存单帧推理对象和关联的媒体与性能信息。"""

    frame_id: int
    media_ref: str
    objects: list[ResultObject]
    meta: dict[str, Any] = field(default_factory=dict)


class BaseRuntime(ABC):
    """定义所有推理后端必须实现的加载、卸载和预测接口。"""

    backend_type: BackendType
    model_task: ModelTaskType = ModelTaskType.DETECT

    def __init__(self) -> None:
        """初始化BaseRuntime实例并准备运行所需状态。"""

        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        """返回推理运行时是否已载入模型。

        Returns:
            当前运行时是否已成功加载模型。
        """

        return self._loaded

    @abstractmethod
    def load_model(self, model_path: Path, config: Any) -> None:
        """根据权重路径和模型配置初始化推理后端。

        Args:
            model_path: 模型权重文件路径。
            config: 当前操作使用的应用或模型配置。
        """
        ...

    @abstractmethod
    def unload_model(self) -> None:
        """释放当前运行时持有的模型和推理资源。"""
        ...

    @abstractmethod
    def predict(self, image: np.ndarray) -> list[ResultObject]:
        """对输入图像执行推理并转换为统一结果对象。

        Args:
            image: 待处理的图像数据。

        Returns:
            统一格式的检测对象列表。
        """
        ...

    @abstractmethod
    def get_classes(self) -> list[str]:
        """返回模型运行时识别到的类别名称列表。

        Returns:
            模型类别名称列表，顺序与类别编号一致。
        """
        ...
