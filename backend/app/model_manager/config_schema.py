"""Model YAML configuration schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RenderConfig(BaseModel):
    color: str = "#2F6FED"
    line_width: int = 2
    label_template: str = "{id}:{class}"


class ModelConfig(BaseModel):
    """Parsed from models/**/*.yaml — independent of weights loading."""

    id: str
    name: str
    backend: str = "yolo"  # yolo | onnx | tensorrt | rknn
    model_path: str
    task: str = "detect"  # detect | segment | pose | ocr | track
    conf: float = 0.45
    iou: float = 0.5
    device: str = "cpu"
    classes: list[str] = Field(default_factory=list)
    class_display: dict[str, str] = Field(default_factory=dict)
    # per-class box colors; mode auto = assign palette by class index
    class_color_mode: str = "auto"  # auto | manual
    class_colors: dict[str, str] = Field(default_factory=dict)
    render: RenderConfig = Field(default_factory=RenderConfig)

    # filled by scanner
    config_path: str | None = None
    source: str = "local"  # local | repository | user

    def display_name_of(self, class_name: str) -> str:
        return self.class_display.get(class_name, class_name)

    def resolve_weight_path(self, root: Path) -> Path:
        p = Path(self.model_path)
        if p.is_absolute():
            return p
        base = Path(self.config_path).parent if self.config_path else root
        return (base / p).resolve()

    def public_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.id,
            "name": self.name,
            "backend": self.backend,
            "task": self.task,
            "conf": self.conf,
            "iou": self.iou,
            "device": self.device,
            "model_path": self.model_path,
            "config_path": self.config_path,
            "source": self.source,
            "classes": list(self.classes),
            "class_display": dict(self.class_display),
            "class_color_mode": self.class_color_mode,
            "class_colors": dict(self.class_colors),
            "render": self.render.model_dump(),
        }
