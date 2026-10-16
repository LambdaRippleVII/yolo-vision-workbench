"""定义模型配置和渲染配置的数据结构。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RenderConfig(BaseModel):
    """保存检测框、标签和文字排版的渲染选项。"""

    color: str = "#2F6FED"
    line_width: int = 2
    label_template: str = "{id}:{class}"


class ModelConfig(BaseModel):
    """保存模型来源、任务类型、权重路径和类别显示配置。"""

    id: str
    name: str
    # 推理后端标识，可选 yolo、onnx、tensorrt 或 rknn。
    backend: str = "yolo"
    model_path: str
    # 模型任务类型，可选 detect、segment、pose、ocr 或 track。
    task: str = "detect"
    conf: float = 0.45
    iou: float = 0.5
    device: str = "cpu"
    classes: list[str] = Field(default_factory=list)
    class_display: dict[str, str] = Field(default_factory=dict)
    # 每个类别的检测框颜色；auto 模式按类别索引自动分配调色板颜色。
    # 类别颜色模式：auto 自动分配，manual 使用配置中的颜色。
    class_color_mode: str = "auto"
    class_colors: dict[str, str] = Field(default_factory=dict)
    render: RenderConfig = Field(default_factory=RenderConfig)
    # 内置模型的来源、作者和许可证元数据。
    source: dict[str, Any] = Field(default_factory=dict)

    # 由模型扫描器补充的来源目录标识。
    config_path: str | None = None
    # 来源目录类型：local、repository 或 user；不等同于 YAML 中的 source 字段。
    source_dir: str = "local"

    def display_name_of(self, class_name: str) -> str:
        """根据类别原名查找用户配置的显示名称。

        Args:
            class_name: 模型提供的类别名称。

        Returns:
            用户配置的类别显示名；没有覆盖项时返回原类别名。
        """

        return self.class_display.get(class_name, class_name)

    def resolve_weight_path(self, root: Path) -> Path:
        """解析权重路径并将相对路径定位到模型目录。

        Args:
            root: 用于解析相对权重路径的模型根目录。

        Returns:
            解析后的权重文件路径。
        """

        p = Path(self.model_path)
        if p.is_absolute():
            return p
        base = Path(self.config_path).parent if self.config_path else root
        return (base / p).resolve()

    def public_dict(self) -> dict[str, Any]:
        """生成可返回给前端的模型公开信息字典。

        Returns:
            包含模型标识、权重、来源、类别和渲染设置的公开字典。
        """

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
            "source_dir": self.source_dir,
            "classes": list(self.classes),
            "class_display": dict(self.class_display),
            "class_color_mode": self.class_color_mode,
            "class_colors": dict(self.class_colors),
            "render": self.render.model_dump(),
        }
