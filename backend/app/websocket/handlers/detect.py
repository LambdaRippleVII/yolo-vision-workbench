"""Detect WebSocket handlers: image / folder inference."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_detect_handlers(hub: WebSocketHub, task_manager) -> None:
    async def on_image(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        media_path = data.get("media_path")
        image_b64 = data.get("image_b64")
        model_ids = data.get("model_ids") or []
        if not media_path and not image_b64:
            return make_error("detect.image", "BAD_REQUEST", "media_path or image_b64 is required", id_=msg.get("id"))
        if not model_ids:
            return make_error("detect.image", "BAD_REQUEST", "model_ids is required", id_=msg.get("id"))

        # resolve b64 paste to a temp file so Task can treat uniformly
        if image_b64 and not media_path:
            import base64
            import tempfile
            from pathlib import Path as P

            raw = base64.b64decode(str(image_b64).split(",")[-1])
            tmp_dir = P(tempfile.gettempdir()) / "yolo-vision-workbench"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp = tmp_dir / f"paste_{int(__import__('time').time()*1000)}.png"
            tmp.write_bytes(raw)
            media_path = str(tmp)

        from pathlib import Path as P2

        # folder path sent to detect.image → run folder task instead
        if media_path and P2(str(media_path)).is_dir():
            folder_task = task_manager.create_folder_task(
                str(media_path),
                [str(m) for m in model_ids],
                overrides=data.get("overrides") or {},
            )
            task_manager.run_folder_task_async(folder_task)
            return make_message(
                "task.created",
                {"ok": True, "task": folder_task.to_dict(), "routed": "folder"},
                id_=msg.get("id"),
            )

        if media_path and not P2(str(media_path)).is_file():
            return make_error(
                "detect.image",
                "MEDIA_NOT_FOUND",
                f"not a valid image file: {media_path}",
                id_=msg.get("id"),
            )

        task = task_manager.create_image_task(
            str(media_path),
            [str(m) for m in model_ids],
            overrides=data.get("overrides") or {},
        )
        try:
            result = task_manager.run_image_task(task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("detect.image failed: {}", exc)
            return make_error(
                "detect.image",
                "INFERENCE_ERROR",
                str(exc),
                id_=msg.get("id"),
                detail={"task_id": task.task_id},
            )

        return make_message(
            "detect.result",
            {"ok": True, **result},
            id_=msg.get("id"),
        )

    async def on_folder(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        folder_path = data.get("folder_path")
        model_ids = data.get("model_ids") or []
        if not folder_path:
            return make_error("detect.folder", "BAD_REQUEST", "folder_path is required", id_=msg.get("id"))
        if not model_ids:
            return make_error("detect.folder", "BAD_REQUEST", "model_ids is required", id_=msg.get("id"))

        from pathlib import Path

        fp = Path(str(folder_path))
        if not fp.is_dir():
            return make_error(
                "detect.folder",
                "MEDIA_NOT_FOUND",
                f"folder not found: {folder_path}",
                id_=msg.get("id"),
            )

        task = task_manager.create_folder_task(
            str(fp),
            [str(m) for m in model_ids],
            overrides=data.get("overrides") or {},
            file_paths=[str(x) for x in (data.get("file_paths") or [])],
        )
        task_manager.run_folder_task_async(task)
        return make_message(
            "task.created",
            {"ok": True, "task": task.to_dict()},
            id_=msg.get("id"),
        )

    hub.register("detect.image", on_image)
    hub.register("detect.folder", on_folder)
