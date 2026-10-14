"""System-level WebSocket handlers: ping, health, hello_ack, shutdown."""

from __future__ import annotations

import os
from typing import Any

from loguru import logger

from app.websocket.protocol import MessageType, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_system_handlers(hub: WebSocketHub, config) -> None:
    async def on_ping(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        return make_message(MessageType.PONG.value, {"server_ts": msg.get("ts")}, id_=msg.get("id"))

    async def on_hello_ack(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        logger.info("client hello_ack: {}", msg.get("data"))
        return None

    async def on_health(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        return make_message(
            MessageType.SYSTEM_HEALTH.value,
            {
                "ok": True,
                "status": "ready",
                "version": config.app_version,
                "pid": os.getpid(),
                "host": config.host,
                "port": config.port,
            },
            id_=msg.get("id"),
        )

    async def on_shutdown(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        logger.info("system.shutdown requested")
        # Reply first; actual process exit is handled by the ASGI lifespan / caller.
        return make_message(
            MessageType.SYSTEM_SHUTDOWN.value,
            {"ok": True},
            id_=msg.get("id"),
        )

    hub.register(MessageType.PING.value, on_ping)
    hub.register(MessageType.SYSTEM_HELLO_ACK.value, on_hello_ack)
    hub.register(MessageType.SYSTEM_HEALTH.value, on_health)
    hub.register(MessageType.SYSTEM_SHUTDOWN.value, on_shutdown)
