"""处理检测对象编辑操作及其持久化请求。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.database import dao
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_ops_handlers(hub: WebSocketHub) -> None:
    """注册检测对象显示和样式编辑消息处理器。

    Args:
        hub: 管理 WebSocket 连接及处理器的服务实例。
    """

    async def on_set_visible(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        task_id = data.get("task_id")
        frame_id = data.get("frame_id")
        object_id = data.get("object_id")
        model_id = data.get("model_id")
        visible = bool(data.get("visible"))
        if task_id is None or frame_id is None or object_id is None:
            return make_error(
                "ops.setVisible",
                "BAD_REQUEST",
                "task_id, frame_id, object_id required",
                id_=msg.get("id"),
            )
        model_id = str(model_id or "")
        try:
            n = dao.set_object_visible(
                str(task_id), int(frame_id), int(object_id), model_id, visible
            )
            op = dao.append_op(
                str(task_id),
                "show_object" if visible else "hide_object",
                frame_id=int(frame_id),
                target_type="object",
                target_id=f"{object_id}:{model_id}",
                payload={"visible": visible, "model_id": model_id},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("setVisible failed: {}", exc)
            return make_error("ops.setVisible", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message(
            "ops.setVisible",
            {"ok": True, "updated": n, "op": op, "visible": visible},
            id_=msg.get("id"),
        )

    async def on_set_style(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        task_id = data.get("task_id")
        frame_id = data.get("frame_id")
        object_id = data.get("object_id")
        model_id = str(data.get("model_id") or "")
        style = data.get("style") or {}
        if task_id is None or frame_id is None or object_id is None:
            return make_error(
                "ops.setStyle",
                "BAD_REQUEST",
                "task_id, frame_id, object_id required",
                id_=msg.get("id"),
            )
        try:
            n = dao.set_object_style(str(task_id), int(frame_id), int(object_id), model_id, style)
            op = dao.append_op(
                str(task_id),
                "modify_style",
                frame_id=int(frame_id),
                target_type="object",
                target_id=f"{object_id}:{model_id}",
                payload={"style": style},
            )
        except Exception as exc:  # noqa: BLE001
            return make_error("ops.setStyle", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message(
            "ops.setStyle",
            {"ok": True, "updated": n, "op": op},
            id_=msg.get("id"),
        )

    async def on_list(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        task_id = (msg.get("data") or {}).get("task_id")
        if not task_id:
            return make_error("ops.list", "BAD_REQUEST", "task_id is required", id_=msg.get("id"))
        return make_message(
            "ops.list",
            {"ok": True, "ops": dao.list_ops(str(task_id))},
            id_=msg.get("id"),
        )

    hub.register("ops.setVisible", on_set_visible)
    hub.register("ops.setStyle", on_set_style)
    hub.register("ops.list", on_list)
