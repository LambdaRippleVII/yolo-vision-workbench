"""按需下载内置模型权重并校验下载结果。"""

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

# 内置模型标识到 Ultralytics 官方权重文件名的映射。
# 用于识别内置权重来源和模型资产名称的仓库标识。
HUB_NAME: dict[str, str] = {
    "coco_yolo11n": "yolo11n.pt",
    "coco_yolo26n": "yolo26n.pt",
    "openimages_yolo8n": "yolov8n-oiv7.pt",
    "objects365_yolo26n": "yolo26n-objv1-150.pt",
}

# 内置模型权重下载所使用的 Ultralytics 资产版本标签。
_ASSET_RELEASE_TAG = "v8.4.0"
# 内置权重资产所在的下载地址前缀。
_ASSET_BASE_URL = f"https://github.com/ultralytics/assets/releases/download/{_ASSET_RELEASE_TAG}"
# 判定下载权重文件有效时要求达到的最小字节数。
MIN_WEIGHT_BYTES = 1000


def _download_ssl_context() -> ssl.SSLContext:
    """构造兼容系统证书的 HTTPS 下载上下文。

    Returns:
        已配置系统证书和 certifi 根证书的 SSL 上下文。
    """

    context = ssl.create_default_context()
    try:
        import certifi
    except ImportError:
        return context
    context.load_verify_locations(cafile=certifi.where())
    return context


def weight_file_available(path: Path) -> bool:
    """检查权重文件是否存在且通过最小文件大小校验。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        文件存在且大小超过最小阈值时返回 True。
    """
    try:
        return path.is_file() and path.stat().st_size > MIN_WEIGHT_BYTES
    except OSError:
        return False


def _download_asset(url: str, dest: Path, progress: Callable[[str], None] | None) -> None:
    """下载单个网络资源到临时文件并汇报进度。

    Args:
        url: 远程模型资源地址。
        dest: 保存模型资源的目标文件路径。
        progress: 接收人类可读下载进度文本的回调函数。

    Raises:
        RuntimeError: 服务器返回错误页面、文件不完整或文件过小时抛出。
    """

    request = Request(url, headers={"User-Agent": "YOLO-Vision-Workbench"})
    # 先写入同目录临时文件，完整性校验通过后再替换正式权重。
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

        # 对照服务端声明长度和最小文件大小，拦截中断响应或错误页面。
        if total and downloaded != total:
            raise RuntimeError(f"文件下载不完整：预期 {total} 字节，收到 {downloaded} 字节")
        if downloaded <= MIN_WEIGHT_BYTES:
            raise RuntimeError(f"下载结果异常（{downloaded} 字节），未保存模型文件")
        # 原子替换可避免模型加载到只写入了一部分的权重文件。
        os.replace(temp, dest)
    finally:
        # 下载失败时清除临时文件，确保用户可以安全重试。
        temp.unlink(missing_ok=True)


def download_weight(
    model_id: str,
    dest: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """按内置模型标识下载权重并在校验后原子替换目标文件。

    Args:
        model_id: 目标模型的唯一标识。
        dest: 保存目标模型权重的文件路径。
        progress: 用于报告下载进度的回调函数。

    Returns:
        下载并校验通过的目标权重路径。

    Raises:
        ValueError: model_id 没有可用的内置资源映射时抛出。
        RuntimeError: 网络请求失败或下载文件校验失败时抛出。
    """
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
            "或在「模型管理」中点击「导入权重」选择本地文件。"
        ) from exc

    logger.info("downloaded builtin model {} -> {}", model_id, dest)
    if progress:
        progress(f"模型权重已保存：{dest.name}")
    return dest


def ensure_builtin(weights_dir: Path, model_ids: list[str]) -> dict[str, Any]:
    """逐项检查并按需下载所请求的内置权重文件。

    Args:
        weights_dir: 保存内置权重的目录。
        model_ids: 本次操作涉及的模型标识列表。

    Returns:
        按模型标识记录成功路径或失败原因的结果字典。
    """

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
    """根据模型标识生成预期的权重文件名。

    Args:
        model_id: 目标模型的唯一标识。

    Returns:
        根据模型标识生成的默认权重文件名。
    """

    mapping = {
        "coco_yolo11n": "yolo11n.pt",
        "coco_yolo26n": "yolo26n.pt",
        "objects365_yolo11n": "objects365_yolo11n.pt",
        "objects365_yolo26n": "objects365_yolo26n.pt",
        "openimages_yolo8n": "openimages_yolov8n.pt",
    }
    return mapping.get(model_id, f"{model_id}.pt")
