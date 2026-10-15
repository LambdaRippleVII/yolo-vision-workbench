"""Import a local weight file into the model library (persist YAML)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from loguru import logger

from app.model_manager.class_persist import persist_classes
from app.model_manager.config_schema import ModelConfig


def _slug(name: str) -> str:
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
    """Copy reference weight into library, write YAML, extract class names from weights."""
    src = Path(weight_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"model file not found: {src}")
    if src.suffix.lower() not in (".pt", ".onnx", ".engine", ".rknn", ".torchscript"):
        raise ValueError(f"unsupported model file: {src.suffix}")

    display = (name or src.stem).strip()
    model_id = _slug(src.stem)
    # unique id
    examples = models_dir / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    weights_dir = examples / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)

    dest_weight = weights_dir / src.name
    if dest_weight.resolve() != src:
        dest_weight.write_bytes(src.read_bytes())

    classes: list[str] = []
    if extract_classes and backend == "yolo" and src.suffix.lower() == ".pt":
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


__all__ = ["import_local_model"]
