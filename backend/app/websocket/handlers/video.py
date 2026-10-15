"""Video detection WebSocket handlers."""

from __future__ import annotations

import asyncio
import base64
import math
from pathlib import Path
from typing import Any

from loguru import logger

from app.utils.image_io import open_video_capture, video_open_error_message
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def _inspect_video(media_path: str) -> dict[str, Any]:
    import cv2

    path = Path(media_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"视频文件不存在或不可访问：{path}")

    capture = open_video_capture(path)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(video_open_error_message(path))
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError("视频已打开，但无法解码首帧；文件可能损坏或编码不受支持。")

        height, width = frame.shape[:2]
        max_dimension = 1440
        scale = min(1.0, max_dimension / max(height, width))
        if scale < 1.0:
            frame = cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))))
        encoded, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
        if not encoded:
            raise RuntimeError("视频首帧已读取，但无法生成预览图。")

        duration = frame_count / fps if frame_count > 0 and fps > 0 and math.isfinite(fps) else None
        return {
            "width": int(width),
            "height": int(height),
            "fps": fps if math.isfinite(fps) else 0,
            "frame_count": frame_count,
            "duration": duration,
            "poster_url": f"data:image/jpeg;base64,{base64.b64encode(buffer.tobytes()).decode('ascii')}",
        }
    finally:
        capture.release()


def register_video_handlers(hub: WebSocketHub, task_manager) -> None:
    async def on_inspect(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        media_path = data.get("media_path")
        if not media_path:
            return make_error("video.inspect", "BAD_REQUEST", "media_path is required", id_=msg.get("id"))
        try:
            preview = await asyncio.to_thread(_inspect_video, str(media_path))
        except Exception as exc:  # noqa: BLE001
            logger.warning("video preview failed path={} error={}", media_path, exc)
            return make_error(
                "video.inspect",
                "VIDEO_PREVIEW_FAILED",
                str(exc),
                id_=msg.get("id"),
                detail={"media_path": str(media_path)},
            )
        return make_message("video.inspect", {"ok": True, **preview}, id_=msg.get("id"))

    async def on_start(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        media_path = data.get("media_path")
        model_ids = data.get("model_ids") or []
        if not media_path:
            return make_error("video.start", "BAD_REQUEST", "media_path is required", id_=msg.get("id"))
        if not model_ids:
            return make_error("video.start", "BAD_REQUEST", "model_ids is required", id_=msg.get("id"))

        skip_frame = int(data.get("skip_frame") or 5)
        box_persistence = int(data.get("box_persistence") or skip_frame)
        # preference: persistence cannot exceed skip interval
        if box_persistence > skip_frame:
            box_persistence = skip_frame

        task = task_manager.create_video_task(
            str(media_path),
            [str(m) for m in model_ids],
            skip_frame=skip_frame,
            box_persistence=box_persistence,
            overrides=data.get("overrides") or {},
        )
        task_manager.run_video_task_async(task)
        logger.info("video task started {}", task.task_id)
        return make_message(
            "task.created",
            {
                "ok": True,
                "task": task.to_dict(),
                "params": {
                    "skip_frame": skip_frame,
                    "box_persistence": box_persistence,
                },
            },
            id_=msg.get("id"),
        )

    async def on_cancel(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        task_id = (msg.get("data") or {}).get("task_id")
        if not task_id:
            return make_error("video.cancel", "BAD_REQUEST", "task_id is required", id_=msg.get("id"))
        try:
            task = task_manager.cancel(str(task_id))
        except KeyError:
            return make_error("video.cancel", "TASK_NOT_FOUND", f"task not found: {task_id}", id_=msg.get("id"))
        return make_message("video.cancel", {"ok": True, "task": task.to_dict()}, id_=msg.get("id"))

    async def on_export(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        source_video = data.get("source_video")
        output_path = data.get("output_path")
        source_task_id = data.get("source_task_id")
        if not source_video:
            return make_error("export.video", "BAD_REQUEST", "source_video is required", id_=msg.get("id"))
        if not output_path:
            return make_error("export.video", "BAD_REQUEST", "output_path is required", id_=msg.get("id"))

        task = task_manager.create_export_task(
            source_task_id=str(source_task_id) if source_task_id else None,
            source_video=str(source_video),
            output_path=str(output_path),
            label_template=str(data.get("label_template") or "{id}:{class}"),
            fps=data.get("fps"),
            hidden_classes=[str(x) for x in (data.get("hidden_classes") or [])],
        )
        task_manager.run_export_task_async(task)
        return make_message(
            "task.created",
            {"ok": True, "task": task.to_dict(), "kind": "export"},
            id_=msg.get("id"),
        )

    hub.register("video.inspect", on_inspect)
    hub.register("video.start", on_start)
    hub.register("video.cancel", on_cancel)
    hub.register("export.video", on_export)
