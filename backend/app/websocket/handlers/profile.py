"""Profile WebSocket handlers."""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.project.profile import ProfilePayload, profile_store
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_profile_handlers(hub: WebSocketHub) -> None:
    async def on_list(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        try:
            profiles = profile_store.list_profiles()
        except Exception as exc:  # noqa: BLE001
            return make_error("profile.list", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("profile.list", {"ok": True, "profiles": profiles}, id_=msg.get("id"))

    async def on_save(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        name = data.get("name") or "未命名配置"
        profile_id = data.get("profile_id")
        payload_raw = data.get("payload") or {}
        try:
            payload = ProfilePayload.model_validate(payload_raw)
            item = profile_store.create(
                str(name),
                payload,
                description=str(data.get("description") or ""),
                profile_id=str(profile_id) if profile_id else None,
                is_default=bool(data.get("is_default")),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("profile.save failed: {}", exc)
            return make_error("profile.save", "BAD_REQUEST", str(exc), id_=msg.get("id"))
        return make_message("profile.save", {"ok": True, "profile": item}, id_=msg.get("id"))

    async def on_apply(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        profile_id = (msg.get("data") or {}).get("profile_id")
        if not profile_id:
            return make_error("profile.apply", "BAD_REQUEST", "profile_id is required", id_=msg.get("id"))
        try:
            item = profile_store.get(str(profile_id))
        except KeyError:
            return make_error("profile.apply", "NOT_FOUND", f"profile not found: {profile_id}", id_=msg.get("id"))
        return make_message("profile.apply", {"ok": True, "profile": item}, id_=msg.get("id"))

    async def on_delete(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        profile_id = (msg.get("data") or {}).get("profile_id")
        if not profile_id:
            return make_error("profile.delete", "BAD_REQUEST", "profile_id is required", id_=msg.get("id"))
        try:
            profile_store.delete(str(profile_id))
        except Exception as exc:  # noqa: BLE001
            return make_error("profile.delete", "INTERNAL", str(exc), id_=msg.get("id"))
        return make_message("profile.delete", {"ok": True, "profile_id": profile_id}, id_=msg.get("id"))

    hub.register("profile.list", on_list)
    hub.register("profile.save", on_save)
    hub.register("profile.apply", on_apply)
    hub.register("profile.delete", on_delete)
