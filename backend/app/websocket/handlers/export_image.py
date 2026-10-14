"""Export image / multi-frame stills WebSocket handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import results as results_db
from app.export.image_export import save_annotated_image, save_frame_images
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_export_image_handlers(hub: WebSocketHub) -> None:
    async def on_save_image(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        source = data.get("source_path")
        output = data.get("output_path")
        task_id = data.get("task_id")
        frame_id = int(data.get("frame_id") or 0)
        label_template = str(data.get("label_template") or "{id}:{class}")
        if not source or not output:
            return make_error(
                "export.image",
                "BAD_REQUEST",
                "source_path and output_path required",
                id_=msg.get("id"),
            )
        objects = data.get("objects")
        if objects is None and task_id is not None:
            objects = results_db.get_frame_objects(str(task_id), frame_id).get("objects")
        try:
            summary = save_annotated_image(
                str(source),
                str(output),
                objects or [],
                label_template=label_template,
            )
        except Exception as exc:  # noqa: BLE001
            return make_error("export.image", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("export.image", {"ok": True, **summary}, id_=msg.get("id"))

    async def on_save_frames(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        task_id = data.get("task_id")
        video_path = data.get("video_path")
        output_dir = data.get("output_dir")
        frame_ids = data.get("frame_ids") or []
        if not task_id or not video_path or not output_dir or not frame_ids:
            return make_error(
                "export.frames",
                "BAD_REQUEST",
                "task_id, video_path, output_dir, frame_ids required",
                id_=msg.get("id"),
            )
        try:
            summary = save_frame_images(
                str(task_id),
                str(video_path),
                str(output_dir),
                [int(x) for x in frame_ids],
                label_template=str(data.get("label_template") or "{id}:{class}"),
            )
        except Exception as exc:  # noqa: BLE001
            return make_error("export.frames", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("export.frames", {"ok": True, **summary}, id_=msg.get("id"))

    hub.register("export.image", on_save_image)
    hub.register("export.frames", on_save_frames)
