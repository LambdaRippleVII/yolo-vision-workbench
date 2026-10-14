"""WebSocket connection manager and message dispatcher."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from app.config import AppConfig
from app.utils.logging import add_ws_sink, remove_ws_sink
from app.websocket.protocol import (
    ErrorPayload,
    MessageType,
    make_error,
    make_message,
)

Handler = Callable[[dict[str, Any], "ConnectionContext"], Awaitable[dict[str, Any] | None]]


class ConnectionContext:
    def __init__(self, websocket: WebSocket, config: AppConfig) -> None:
        self.websocket = websocket
        self.config = config
        self._closed = False

    async def send(self, message: dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            await self.websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws send failed: {}", exc)

    def mark_closed(self) -> None:
        self._closed = True


class WebSocketHub:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._handlers: dict[str, Handler] = {}
        self._connections: set[ConnectionContext] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self, type_: str, handler: Handler) -> None:
        self._handlers[type_] = handler

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def handle_connection(self, websocket: WebSocket) -> None:
        await websocket.accept()
        ctx = ConnectionContext(websocket, self.config)
        self._connections.add(ctx)
        logger.info("ws connected total={}", len(self._connections))

        def log_sink(record: dict) -> None:
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    ctx.send(make_message(MessageType.LOG_MESSAGE.value, record)),
                    self._loop,
                )

        add_ws_sink(log_sink)

        try:
            await ctx.send(
                make_message(
                    MessageType.SYSTEM_HELLO.value,
                    {
                        "server_version": self.config.app_version,
                        "protocol_version": self.config.protocol_version,
                        "features": ["system", "health", "log"],
                    },
                )
            )
            while True:
                raw = await websocket.receive_text()
                await self._dispatch(raw, ctx)
        except WebSocketDisconnect:
            logger.info("ws disconnected")
        except Exception as exc:  # noqa: BLE001
            logger.exception("ws connection error: {}", exc)
        finally:
            remove_ws_sink(log_sink)
            ctx.mark_closed()
            self._connections.discard(ctx)
            logger.info("ws closed total={}", len(self._connections))

    async def _dispatch(self, raw: str, ctx: ConnectionContext) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await ctx.send(
                make_error(MessageType.ERROR.value, "BAD_REQUEST", "invalid JSON")
            )
            return

        if not isinstance(payload, dict) or "type" not in payload:
            await ctx.send(
                make_error(
                    MessageType.ERROR.value,
                    "BAD_REQUEST",
                    "message must be an object with 'type'",
                )
            )
            return

        type_ = str(payload.get("type", ""))
        msg_id = payload.get("id")
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            await ctx.send(
                make_error(
                    type_,
                    "BAD_REQUEST",
                    "'data' must be an object",
                    id_=msg_id if isinstance(msg_id, str) else None,
                )
            )
            return

        handler = self._handlers.get(type_)
        if handler is None:
            await ctx.send(
                make_error(
                    type_,
                    "BAD_REQUEST",
                    f"unknown message type: {type_}",
                    id_=msg_id if isinstance(msg_id, str) else None,
                )
            )
            return

        try:
            result = await handler(
                {
                    "type": type_,
                    "id": msg_id,
                    "data": data,
                    "ts": payload.get("ts"),
                },
                ctx,
            )
            if result is not None:
                await ctx.send(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("handler failed type={}", type_)
            await ctx.send(
                make_error(
                    type_,
                    "INTERNAL",
                    str(exc),
                    id_=msg_id if isinstance(msg_id, str) else None,
                )
            )

    async def broadcast(self, message: dict[str, Any]) -> None:
        for ctx in list(self._connections):
            await ctx.send(message)
