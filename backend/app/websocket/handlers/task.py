"""Task list / detail WebSocket handlers."""

from __future__ import annotations

from typing import Any

from app.database import dao
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_task_handlers(hub: WebSocketHub, task_manager) -> None:
    async def on_list(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        memory_tasks = task_manager.list_tasks()
        # Prefer DB as source of truth when available
        try:
            db_tasks = dao.list_tasks(limit=100)
            by_id = {t["task_id"]: t for t in db_tasks}
            merged = []
            for t in memory_tasks:
                row = by_id.pop(t["task_id"], None)
                merged.append({**t, **(row or {})})
            merged.extend(by_id.values())
        except Exception:
            merged = memory_tasks
        return make_message(
            "task.list",
            {"ok": True, "tasks": merged},
            id_=msg.get("id"),
        )

    async def on_get(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        task_id = msg.get("data", {}).get("task_id")
        if not task_id:
            return make_error("task.get", "BAD_REQUEST", "task_id is required", id_=msg.get("id"))
        task = task_manager.get(str(task_id))
        if task is None:
            return make_error("task.get", "TASK_NOT_FOUND", f"task not found: {task_id}", id_=msg.get("id"))
        return make_message("task.get", {"ok": True, "task": task.to_dict()}, id_=msg.get("id"))

    async def on_cancel(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        task_id = msg.get("data", {}).get("task_id")
        if not task_id:
            return make_error("task.cancel", "BAD_REQUEST", "task_id is required", id_=msg.get("id"))
        try:
            task = task_manager.cancel(str(task_id))
        except KeyError:
            return make_error("task.cancel", "TASK_NOT_FOUND", f"task not found: {task_id}", id_=msg.get("id"))
        return make_message("task.cancel", {"ok": True, "task": task.to_dict()}, id_=msg.get("id"))

    hub.register("task.list", on_list)
    hub.register("task.get", on_get)
    hub.register("task.cancel", on_cancel)
