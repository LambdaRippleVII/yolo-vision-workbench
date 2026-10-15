"""Download builtin Ultralytics weights into the application's writable model store."""

from __future__ import annotations

from http.client import IncompleteRead
import os
import ssl
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from loguru import logger

# model_id -> Ultralytics release asset name
HUB_NAME: dict[str, str] = {
    "coco_yolo11n": "yolo11n.pt",
    "coco_yolo26n": "yolo26n.pt",
    "openimages_yolo8n": "yolov8n-oiv7.pt",
    "objects365_yolo26n": "yolo26n-objv1-150.pt",
}

_ASSET_RELEASE_TAG = "v8.4.0"
_ASSET_BASE_URL = f"https://github.com/ultralytics/assets/releases/download/{_ASSET_RELEASE_TAG}"
MIN_WEIGHT_BYTES = 1000


def _download_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return context
    context.load_verify_locations(cafile=certifi.where())
    return context


def weight_file_available(path: Path) -> bool:
    """Treat empty and obviously partial files as missing weights."""
    try:
        return path.is_file() and path.stat().st_size > MIN_WEIGHT_BYTES
    except OSError:
        return False


def _download_asset(url: str, dest: Path, progress: Callable[[str], None] | None) -> None:
    request = Request(url, headers={"User-Agent": "YOLO-Vision-Workbench"})
    temp = dest.with_name(f".{dest.name}.{uuid.uuid4().hex}.part")
    downloaded = 0
    last_progress = -1

    try:
        with (
            urlopen(request, timeout=30, context=_download_ssl_context()) as response,
            temp.open("wb") as out,
        ):
            if response.headers.get_content_type() == "text/html":
                raise RuntimeError("官方仓库返回了网页而不是模型文件")
            total = int(response.headers.get("Content-Length", "0") or 0)
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)

                if progress:
                    if total:
                        percent = min(100, int(downloaded * 100 / total))
                        if percent >= last_progress + 10:
                            progress(f"正在下载 {dest.name}：{percent}%")
                            last_progress = percent
                    else:
                        progress(f"正在下载 {dest.name}：{downloaded / (1024 * 1024):.1f} MB")

        if total and downloaded != total:
            raise RuntimeError(f"文件下载不完整：预期 {total} 字节，收到 {downloaded} 字节")
        if downloaded <= MIN_WEIGHT_BYTES:
            raise RuntimeError(f"下载结果异常（{downloaded} 字节），未保存模型文件")
        os.replace(temp, dest)
    finally:
        temp.unlink(missing_ok=True)


def download_weight(
    model_id: str,
    dest: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Download a known builtin checkpoint atomically; no torch import is needed."""
    if weight_file_available(dest):
        return dest
    if model_id not in HUB_NAME:
        raise ValueError(f"模型「{model_id}」没有可下载的内置权重，请导入本地模型文件")

    dest.parent.mkdir(parents=True, exist_ok=True)

    asset_name = HUB_NAME[model_id]
    if progress:
        progress(f"正在连接 Ultralytics 官方模型仓库：{asset_name}…")
    try:
        _download_asset(f"{_ASSET_BASE_URL}/{asset_name}", dest, progress)
    except (HTTPError, URLError, IncompleteRead, OSError, RuntimeError) as exc:
        logger.warning("download {} failed: {}", asset_name, exc)
        raise RuntimeError(
            f"模型「{model_id}」权重下载失败：{exc}。请检查网络/代理后重试，"
            "或通过「添加模型」导入本地权重。"
        ) from exc

    logger.info("downloaded builtin model {} -> {}", model_id, dest)
    if progress:
        progress(f"模型权重已保存：{dest.name}")
    return dest


def ensure_builtin(weights_dir: Path, model_ids: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for model_id in model_ids:
        dest = weights_dir / _default_filename(model_id)
        try:
            download_weight(model_id, dest)
            results[model_id] = {"ok": True, "path": str(dest)}
        except Exception as exc:  # noqa: BLE001
            results[model_id] = {"ok": False, "error": str(exc)}
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
