"""定义 WebSocket 消息封装、错误负载和时间戳。"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
# 系统级握手、心跳和健康检查消息。
    """集中列出前后端通信使用的消息类型。"""

    SYSTEM_HELLO = "system.hello"
    SYSTEM_HELLO_ACK = "system.hello_ack"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_SHUTDOWN = "system.shutdown"
    PING = "ping"
    PONG = "pong"
    LOG_MESSAGE = "log.message"
    ERROR = "error"


class ErrorPayload(BaseModel):
    """描述统一协议中的错误码、消息和附加信息。"""

    code: str
    message: str
    detail: dict[str, Any] | None = None


class Envelope(BaseModel):
    """定义 WebSocket 消息的类型、标识、数据和时间戳结构。"""

    type: str
    id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    ts: int = Field(default_factory=lambda: int(time.time() * 1000))
    error: ErrorPayload | None = None


def make_message(
    type_: str,
    data: dict[str, Any] | None = None,
    *,
    id_: str | None = None,
    error: ErrorPayload | None = None,
) -> dict[str, Any]:
    """创建包含类型、数据、消息标识和时间戳的协议封装。

    Args:
        type_: 消息或错误的协议类型。
        data: 消息携带的业务数据。
        id_: 本次 WebSocket 请求的关联标识。
        error: 需要记录或返回的错误描述。

    Returns:
        可直接序列化并发送给客户端的消息字典。
    """

    env = Envelope(type=type_, id=id_, data=data or {}, error=error)
    return env.model_dump()


def make_error(
    type_: str,
    code: str,
    message: str,
    *,
    id_: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """将业务错误转换为前端可解析的统一错误消息。

    Args:
        type_: 消息或错误的协议类型。
        code: 前端可识别的业务错误代码。
        message: 待发送或解析的协议消息。
        id_: 本次 WebSocket 请求的关联标识。
        detail: 供排查错误使用的附加信息。

    Returns:
        包含统一错误负载的协议消息字典。
    """

    return make_message(
        type_,
        {"ok": False},
        id_=id_,
        error=ErrorPayload(code=code, message=message, detail=detail),
    )


def now_ms() -> int:
    """返回当前 Unix 毫秒时间戳。

    Returns:
        当前 Unix 时间对应的毫秒整数。
    """

    return int(time.time() * 1000)
