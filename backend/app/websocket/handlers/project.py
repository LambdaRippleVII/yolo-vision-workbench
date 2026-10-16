"""处理项目列表、创建、打开和切换请求。"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_project_handlers(hub: WebSocketHub, project_store) -> None:
    """注册项目创建、列表和切换消息处理器。

    Args:
        hub: 管理 WebSocket 连接及处理器的服务实例。
        project_store: 负责项目目录和元数据持久化的存储实例。
    """

    async def on_list(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        projects = project_store.list_projects()
        return make_message(
            "project.list",
            {
                "ok": True,
                "projects": projects,
                "current_project_id": project_store.current_id,
            },
            id_=msg.get("id"),
        )

    async def on_create(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        name = data.get("name")
        if not name:
            return make_error("project.create", "BAD_REQUEST", "name is required", id_=msg.get("id"))
        try:
            meta = project_store.create(str(name), description=str(data.get("description") or ""))
        except ValueError as exc:
            return make_error("project.create", "BAD_REQUEST", str(exc), id_=msg.get("id"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("project.create failed")
            return make_error("project.create", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("project.create", {"ok": True, "project": meta}, id_=msg.get("id"))

    async def on_open(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        project_id = (msg.get("data") or {}).get("project_id")
        if not project_id:
            return make_error("project.open", "BAD_REQUEST", "project_id is required", id_=msg.get("id"))
        try:
            meta = project_store.open(str(project_id))
        except FileNotFoundError:
            return make_error(
                "project.open",
                "NOT_FOUND",
                f"project not found: {project_id}",
                id_=msg.get("id"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("project.open failed")
            return make_error("project.open", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message(
            "project.open",
            {"ok": True, "project": meta, "current_project_id": project_store.current_id},
            id_=msg.get("id"),
        )

    async def on_current(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        return make_message(
            "project.current",
            {"ok": True, "project": project_store.current(), "current_project_id": project_store.current_id},
            id_=msg.get("id"),
        )

    async def on_save(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        project_id = data.get("project_id") or project_store.current_id
        patch = data.get("patch") or {}
        try:
            meta = project_store.save_meta(str(project_id), patch)
        except Exception as exc:  # noqa: BLE001
            return make_error("project.save", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("project.save", {"ok": True, "project": meta}, id_=msg.get("id"))

    hub.register("project.list", on_list)
    hub.register("project.create", on_create)
    hub.register("project.open", on_open)
    hub.register("project.current", on_current)
    hub.register("project.save", on_save)
