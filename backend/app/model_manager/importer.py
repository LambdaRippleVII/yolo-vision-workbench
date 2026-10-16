"""导入本地模型权重，或为已有模型关联权重文件。"""

from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

import yaml
from loguru import logger

from app.model_manager.class_persist import persist_classes
from app.model_manager.config_schema import ModelConfig
from app.model_manager.downloader import MIN_WEIGHT_BYTES, weight_file_available


def _slug(name: str) -> str:
    """把模型名称转换为适合写入配置和路径的标识。

    Args:
        name: 新模型在界面中显示的名称；未提供时使用权重文件名。

    Returns:
        可安全写入配置文件和目录的模型标识。
    """

    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", (name or "model").strip())
    return s.strip("_") or "model"


def import_local_model(
    weight_path: str | Path,
    *,
    models_dir: Path,
    name: str | None = None,
    backend: str = "yolo",
    task: str = "detect",
    extract_classes: bool = True,
) -> dict:
    """复制本地权重并创建对应模型配置。

    Args:
        weight_path: 本地模型权重文件路径。
        models_dir: 本地模型及权重文件的根目录。
        name: 新模型在界面中显示的名称；未提供时使用权重文件名。
        backend: 推理后端类型或后端标识。
        task: 模型支持的任务类型，例如 ``detect`` 或 ``segment``。
        extract_classes: 导入时是否尝试从权重读取类别名称。

    Returns:
        包含模型标识、配置路径、权重路径和类别数量的导入结果。

    Raises:
        FileNotFoundError: 权重文件不存在时抛出。
        ValueError: 权重扩展名或文件内容不符合支持格式时抛出。
    """
    src = Path(weight_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"model file not found: {src}")
    if src.suffix.lower() not in (".pt", ".onnx", ".engine", ".rknn", ".torchscript"):
        raise ValueError(f"unsupported model file: {src.suffix}")

    display = (name or src.stem).strip()
    model_id = _slug(src.stem)
    # 为权重和模型配置准备用户可写的示例模型目录。
    examples = models_dir / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    weights_dir = examples / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    dest_weight = weights_dir / src.name
    if dest_weight.resolve() != src:
        dest_weight.write_bytes(src.read_bytes())

    classes: list[str] = []
    if extract_classes and backend == "yolo" and src.suffix.lower() == ".pt":
        # 类别读取仅用于预填模型信息；失败时不影响权重导入。
        try:
            from ultralytics import YOLO

            model = YOLO(str(src))
            names = getattr(model, "names", None)
            if isinstance(names, dict):
                classes = [str(names[k]) for k in sorted(names.keys())]
            elif isinstance(names, list):
                classes = [str(n) for n in names]
            logger.info("extracted {} classes from {}", len(classes), src)
        except Exception as exc:  # noqa: BLE001
            logger.warning("extract classes failed: {}", exc)

    cfg_path = examples / f"{model_id}.yaml"
    if cfg_path.exists():
        # 不覆盖已存在的模型配置，为重复导入的模型分配独立标识。
        model_id = f"{model_id}_{int(Path().stat().st_mtime)}" if False else f"{model_id}_imported"
        cfg_path = examples / f"{model_id}.yaml"

    payload = {
        "id": model_id,
        "name": display,
        "backend": backend,
        "model_path": f"weights/{dest_weight.name}",
        "task": task,
        "conf": 0.4,
        "iou": 0.5,
        "device": "cpu",
        "source": {
            "dataset": "自定义",
            "author": "用户导入",
            "license": "见权重文件自身许可",
            "note": f"从本地导入: {src}",
        },
        "class_color_mode": "auto",
        "render": {"color": "#2F6FED", "line_width": 2, "label_template": "{id}:{class}"},
    }
    if classes:
        payload["classes"] = classes

    cfg_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    logger.info("imported model {} -> {}", model_id, cfg_path)
    return {
        "model_id": model_id,
        "name": display,
        "config_path": str(cfg_path),
        "weight_path": str(dest_weight),
        "class_count": len(classes),
    }


def attach_model_weights(weight_path: str | Path, model: ModelConfig) -> dict[str, str]:
    """把已选权重文件关联到现有模型并更新配置。

    Args:
        weight_path: 本地模型权重文件路径。
        model: 要关联新权重的现有模型配置。

    Returns:
        包含模型标识和最终权重路径的关联结果。

    Raises:
        FileNotFoundError: 待导入权重文件不存在时抛出。
        ValueError: 文件格式、大小或目标模型配置不匹配时抛出。
    """

    src = Path(weight_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"model file not found: {src}")
    if src.suffix.lower() not in (".pt", ".onnx", ".engine", ".rknn", ".torchscript"):
        raise ValueError(f"unsupported model file: {src.suffix}")
    if src.stat().st_size <= MIN_WEIGHT_BYTES:
        raise ValueError("所选权重文件太小或不完整。")

    if not model.config_path:
        raise ValueError(f"model config path is unavailable: {model.id}")
    config_path = Path(model.config_path).resolve()
    destination = model.resolve_weight_path(config_path.parent)
    if src.suffix.lower() != destination.suffix.lower():
        expected = destination.suffix or "无扩展名"
        raise ValueError(f"该模型需要 {expected} 格式的权重，请选择相同格式的文件。")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # 先复制到目标目录内的临时文件，校验后再替换配置指定的正式权重。
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        if src != destination:
            shutil.copyfile(src, temporary)
            if temporary.stat().st_size <= MIN_WEIGHT_BYTES:
                raise ValueError("复制后的权重文件不完整。")
            temporary.replace(destination)
        # 使用统一校验规则确认目标文件可供后续模型加载。
        if not weight_file_available(destination):
            raise ValueError(f"导入后的权重不可用：{destination}")
    finally:
        # 无论导入成功与否都清理临时副本。
        temporary.unlink(missing_ok=True)

    logger.info("attached model weights {} -> {}", src, destination)
    return {"model_id": model.id, "weight_path": str(destination)}


# 显式声明此模块向其他模块公开的接口名称。
__all__ = ["attach_model_weights", "import_local_model"]
