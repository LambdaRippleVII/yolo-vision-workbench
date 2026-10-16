"""处理摄像头连接、实时推理和录制控制消息。"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from app.task.stream_task import StreamSession
from app.task.manager import TaskManager
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_camera_handlers(hub: WebSocketHub, model_manager, task_manager: TaskManager) -> None:
    """注册摄像头连接、模型选择和录制相关消息处理器。

    Args:
        hub: 管理 WebSocket 连接及处理器的服务实例。
        model_manager: 负责查询和加载模型的管理器。
        task_manager: 负责创建和调度任务的管理器。
    """

    sessions: dict[str, StreamSession] = {}

    def emit_to_loop(message: dict[str, Any]) -> None:
        loop = getattr(hub, "_loop", None)
        if loop and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(hub.broadcast(message), loop)

    async def on_open(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        source_type = str(data.get("source_type") or "usb")
        model_ids = [str(m) for m in (data.get("model_ids") or [])]
        skip_frame = int(data.get("skip_frame") or 5)
        box_persistence = int(data.get("box_persistence") or skip_frame)
        if box_persistence > skip_frame:
            box_persistence = skip_frame

        if source_type == "rtsp":
            source: str | int = str(data.get("source") or data.get("url") or "")
            if not source:
                return make_error("camera.open", "BAD_REQUEST", "rtsp url required", id_=msg.get("id"))
        else:
            source = int(data.get("device_index") or 0)

        stream_id = f"st_{uuid.uuid4().hex[:10]}"
        session = StreamSession(
            stream_id=stream_id,
            source=source,
            model_ids=model_ids,
            skip_frame=skip_frame,
            box_persistence=box_persistence,
            emit=emit_to_loop,
            model_manager=model_manager,
        )
        sessions[stream_id] = session
        session.start()
        logger.info("camera open {} source={}", stream_id, source)
        return make_message(
            "camera.open",
            {
                "ok": True,
                "stream_id": stream_id,
                "source_type": source_type,
                "params": {"skip_frame": skip_frame, "box_persistence": box_persistence},
            },
            id_=msg.get("id"),
        )

    async def on_close(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        stream_id = (msg.get("data") or {}).get("stream_id")
        if not stream_id or stream_id not in sessions:
            return make_error("camera.close", "NOT_FOUND", f"stream not found: {stream_id}", id_=msg.get("id"))
        session = sessions.pop(str(stream_id))
        session.stop()
        return make_message(
            "camera.close",
            {
                "ok": True,
                "stream_id": stream_id,
                "frames": session.frame_count,
                "detect_count": session.detect_count,
            },
            id_=msg.get("id"),
        )

    async def on_status(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        items = [
            {
                "stream_id": s.stream_id,
                "frames": s.frame_count,
                "detect_count": s.detect_count,
                "error": s.last_error,
            }
            for s in sessions.values()
        ]
        return make_message("camera.status", {"ok": True, "streams": items}, id_=msg.get("id"))

    async def on_record(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        stream_id = data.get("stream_id")
        action = str(data.get("action") or "")
        session = sessions.get(str(stream_id)) if stream_id else None
        if not session:
            return make_error("camera.record", "NOT_FOUND", f"stream not found: {stream_id}", id_=msg.get("id"))
        if action == "start":
            path = str(data.get("output_path") or "")
            if not path:
                return make_error("camera.record", "BAD_REQUEST", "output_path required", id_=msg.get("id"))
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            fps = data.get("fps")
            try:
                fps_val = float(fps) if fps is not None else None
            except (TypeError, ValueError):
                fps_val = None
        # 创建任务以持久化结果，后续可直接编辑而无需重新检测。
            task = task_manager.create_video_task(
                path,
                list(session.model_ids),
                skip_frame=session.skip_frame,
                box_persistence=session.box_persistence,
                overrides={"source": "camera_record", "stream_id": str(stream_id), "fps": fps_val},
            )
            from app.database import dao as db_dao

            db_dao.upsert_task(task.to_dict())
            session.start_recording(path, fps=fps_val, task_id=task.task_id)
            return make_message(
                "camera.record",
                {
                    "ok": True,
                    "action": "start",
                    "stream_id": stream_id,
                    "output_path": path,
                    "task_id": task.task_id,
                    "fps": fps_val or 20.0,
                },
                id_=msg.get("id"),
            )
        if action == "stop":
            out = session.stop_recording()
            if out.get("task_id"):
                try:
                    from app.database import dao as db_dao
                    from app.task.base import TaskStatus

                    t = task_manager.get(str(out["task_id"]))
                    if t:
                        t.result_ref = out.get("output_path")
                        t.progress = 1.0
        # 如果录制尚未真正开始，任务可能仍处于 PENDING 状态。
                        if t.status == TaskStatus.PENDING:
                            t.transition(TaskStatus.RUNNING)
                        if t.status == TaskStatus.RUNNING:
                            t.transition(TaskStatus.COMPLETED)
                        db_dao.upsert_task(t.to_dict())
                except Exception as exc:  # noqa: BLE001
                    logger.warning("finalize record task failed: {}", exc)
            return make_message(
                "camera.record",
                {
                    "ok": True,
                    "action": "stop",
                    "stream_id": stream_id,
                    **out,
                },
                id_=msg.get("id"),
            )
        return make_error("camera.record", "BAD_REQUEST", "action must be start|stop", id_=msg.get("id"))

    async def on_set_models(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        stream_id = data.get("stream_id")
        session = sessions.get(str(stream_id)) if stream_id else None
        if not session:
            return make_error("camera.setModels", "NOT_FOUND", f"stream not found: {stream_id}", id_=msg.get("id"))
        model_ids = [str(m) for m in (data.get("model_ids") or [])]
        # 为新选择的模型确认推理运行时已经准备好。
        for mid in model_ids:
            if mid not in model_manager._loaded:
                try:
                    model_manager.load(mid)
                except Exception as exc:  # noqa: BLE001
                    return make_error(
                        "camera.setModels",
                        "MODEL_LOAD_FAILED",
                        f"{mid}: {exc}",
                        id_=msg.get("id"),
                    )
        current = session.set_model_ids(model_ids)
        return make_message(
            "camera.setModels",
            {"ok": True, "stream_id": stream_id, "model_ids": current},
            id_=msg.get("id"),
        )

    hub.register("camera.open", on_open)
    hub.register("camera.close", on_close)
    hub.register("camera.status", on_status)
    hub.register("camera.record", on_record)
    hub.register("camera.setModels", on_set_models)
