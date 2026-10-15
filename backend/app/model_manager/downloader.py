"""Download missing builtin model weights (Ultralytics hub names)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable

from loguru import logger

# model_id -> ultralytics hub / well-known filename
HUB_NAME: dict[str, str] = {
    "coco_yolo11n": "yolo11n.pt",
    "coco_yolo26n": "yolo26n.pt",
    "openimages_yolo8n": "yolov8n-oiv7.pt",
    # objects365 hub name may differ; try common aliases
    "objects365_yolo11n": "yolo11n-objects365.pt",
    "objects365_yolo26n": "yolo26n-objects365.pt",
}

ALIASES: dict[str, list[str]] = {
    "objects365_yolo11n": ["yolo11n-objects365.pt", "yolov8n-objects365.pt"],
    "objects365_yolo26n": ["yolo26n-objects365.pt", "yolov8s-objects365.pt"],
    "openimages_yolo8n": ["yolov8n-oiv7.pt", "yolo11n-oiv7.pt"],
}


def download_weight(
    model_id: str,
    dest: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Resolve or download weight into dest. Raise RuntimeError with Chinese message on failure."""
    if dest.exists() and dest.stat().st_size > 1000:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    names = ALIASES.get(model_id) or [HUB_NAME.get(model_id, f"{model_id}.pt")]
    last_err: Exception | None = None
    for hub in names:
        try:
            progress and progress(f"正在下载 {hub}…")
            from ultralytics import YOLO  # local import

            model = YOLO(hub)
            src = Path(hub)
            if src.exists():
                shutil.copy2(src, dest)
            else:
                # ultralytics may leave file in cwd
                found = list(Path.cwd().glob(hub))
                if found:
                    shutil.copy2(found[0], dest)
                else:
                    raise FileNotFoundError(f"下载后未找到权重文件 {hub}")
            logger.info("downloaded {} -> {}", hub, dest)
            progress and progress(f"已下载 {dest.name}")
            return dest
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("download {} failed: {}", hub, exc)
    raise RuntimeError(
        f"模型「{model_id}」权重下载失败：{last_err}。"
        f"可手动将 {dest.name} 放入 models/examples/weights/ 后重试。"
    )


def ensure_builtin(weights_dir: Path, model_ids: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for mid in model_ids:
        dest = weights_dir / f"{mid.replace('coco_', '')}.pt"
        # normalize dest names to yaml model_path
        dest = weights_dir / (_default_filename(mid))
        try:
            download_weight(mid, dest)
            results[mid] = {"ok": True, "path": str(dest)}
        except Exception as exc:  # noqa: BLE001
            results[mid] = {"ok": False, "error": str(exc)}
    return results


def _default_filename(model_id: str) -> str:
    mapping = {
        "coco_yolo11n": "yolo11n.pt",
        "coco_yolo26n": "yolo26n.pt",
        "objects365_yolo11n": "objects365_yolo11n.pt",
        "objects365_yolo26n": "objects365_yolo26n.pt",
        "openimages_yolo8n": "openimages_yolov8n.pt",
    }
    return mapping.get(model_id, f"{model_id}.pt")
