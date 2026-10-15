"""Result query WebSocket handlers: timeline / frame objects / frame preview."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from app.database import results as results_db
from app.utils.image_io import open_video_capture, video_open_error_message
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_result_handlers(hub: WebSocketHub) -> None:
    async def on_frames(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        task_id = (msg.get("data") or {}).get("task_id")
        if not task_id:
            return make_error("result.frames", "BAD_REQUEST", "task_id is required", id_=msg.get("id"))
        frames = results_db.list_task_frames(str(task_id))
        return make_message(
            "result.frames",
            {"ok": True, "task_id": task_id, "frames": frames},
            id_=msg.get("id"),
        )

    async def on_frame(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        task_id = data.get("task_id")
        frame_id = data.get("frame_id")
        if task_id is None or frame_id is None:
            return make_error(
                "result.frame",
                "BAD_REQUEST",
                "task_id and frame_id are required",
                id_=msg.get("id"),
            )
        payload = results_db.get_frame_objects(str(task_id), int(frame_id))
        return make_message("result.frame", {"ok": True, **payload}, id_=msg.get("id"))

    async def on_preview(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        video_path = data.get("video_path")
        frame_id = int(data.get("frame_id") or 0)
        if not video_path:
            return make_error(
                "result.preview",
                "BAD_REQUEST",
                "video_path is required",
                id_=msg.get("id"),
            )
        path = Path(str(video_path))
        if not path.exists():
            return make_error(
                "result.preview",
                "MEDIA_NOT_FOUND",
                f"video not found: {video_path}",
                id_=msg.get("id"),
            )
        jpeg = results_db.extract_video_frame_jpeg(str(path), frame_id)
        if jpeg is None:
            return make_error(
                "result.preview",
                "INFERENCE_ERROR",
                f"cannot extract frame {frame_id}",
                id_=msg.get("id"),
            )
        b64 = base64.b64encode(jpeg).decode("ascii")
        return make_message(
            "result.preview",
            {
                "ok": True,
                "frame_id": frame_id,
                "jpeg_b64": b64,
                "data_url": f"data:image/jpeg;base64,{b64}",
            },
            id_=msg.get("id"),
        )

    async def on_thumbs(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        video_path = data.get("video_path")
        frame_ids = data.get("frame_ids") or []
        if not video_path or not frame_ids:
            return make_error("result.thumbs", "BAD_REQUEST", "video_path and frame_ids required", id_=msg.get("id"))
        import base64

        import cv2

        from app.utils.image_io import imread_unicode  # noqa: F401

        cap = open_video_capture(str(video_path))
        if not cap.isOpened():
            return make_error(
                "result.thumbs",
                "MEDIA_NOT_FOUND",
                video_open_error_message(str(video_path)),
                id_=msg.get("id"),
            )
        thumbs = []
        try:
            for fid in frame_ids[:200]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(fid))
                ok, frame = cap.read()
                if not ok:
                    thumbs.append({"frame_id": int(fid), "thumb_url": ""})
                    continue
                h, w = frame.shape[:2]
                scale = min(1.0, 96 / max(h, w))
                if scale < 1.0:
                    frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
                ok2, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 65])
                b64 = base64.b64encode(buf.tobytes()).decode("ascii") if ok2 else ""
                thumbs.append(
                    {
                        "frame_id": int(fid),
                        "thumb_url": f"data:image/jpeg;base64,{b64}" if b64 else "",
                    }
                )
        finally:
            cap.release()
        return make_message("result.thumbs", {"ok": True, "thumbs": thumbs}, id_=msg.get("id"))

    hub.register("result.frames", on_frames)
    hub.register("result.frame", on_frame)
    hub.register("result.preview", on_preview)
    hub.register("result.thumbs", on_thumbs)
