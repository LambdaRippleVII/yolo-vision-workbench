"""管理 WebSocket 客户端连接、消息分发和广播。"""

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

# 统一描述 WebSocket 业务处理器的异步函数签名。
Handler = Callable[[dict[str, Any], "ConnectionContext"], Awaitable[dict[str, Any] | None]]


class ConnectionContext:
    """保存单个 WebSocket 连接及其发送和关闭状态。"""

    def __init__(self, websocket: WebSocket, config: AppConfig) -> None:
        """保存客户端连接及后端运行配置。

        Args:
            websocket: 当前客户端的 WebSocket 连接对象。
            config: 当前操作使用的应用或模型配置。
        """

        self.websocket = websocket
        self.config = config
        self._closed = False

    async def send(self, message: dict[str, Any]) -> None:
        """发送一条协议消息，并在关闭状态下跳过写入。

        Args:
            message: 待发送或解析的协议消息。
        """

        if self._closed:
            return
        try:
            await self.websocket.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws send failed: {}", exc)

    def mark_closed(self) -> None:
        """记录客户端连接已经关闭。"""

        self._closed = True


class WebSocketHub:
    """注册消息处理器并管理 WebSocket 广播与请求分发。"""

    def __init__(self, config: AppConfig) -> None:
        """初始化连接集合、消息处理器和事件循环引用。

        Args:
            config: 当前操作使用的应用或模型配置。
        """

        self.config = config
        self._handlers: dict[str, Handler] = {}
        self._connections: set[ConnectionContext] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def register(self, type_: str, handler: Handler) -> None:
        """按消息类型保存对应的处理回调。

        Args:
            type_: 消息或错误的协议类型。
            handler: 接收消息数据和连接上下文的处理函数。
        """

        self._handlers[type_] = handler

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定服务运行的异步事件循环。

        Args:
            loop: 用于把工作线程事件投递到 WebSocket 协程的事件循环。
        """

        self._loop = loop

    async def handle_connection(self, websocket: WebSocket) -> None:
        """接入客户端并处理连接期间的消息与清理。

        Args:
            websocket: 当前客户端的 WebSocket 连接对象。
        """

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

        # 每个连接独立订阅日志，并在 finally 中移除对应回调。
        add_ws_sink(log_sink)

        try:
            # 首条消息声明协议版本和功能，前端据此初始化连接状态。
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
        """验证请求并调用对应处理器后生成响应。

        Args:
            raw: 尚未解析的输入消息或原始值。
            ctx: 当前 WebSocket 客户端的连接上下文。
        """

        try:
            # 依次校验 JSON、消息封装、data 类型和已注册处理器。
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
        """向所有当前连接发送相同的消息。

        Args:
            message: 待发送或解析的协议消息。
        """

        for ctx in list(self._connections):
            await ctx.send(message)
