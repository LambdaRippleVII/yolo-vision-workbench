"""WebSocket message envelope and types.

Envelope:
    {"type": "...", "id": "..."|null, "data": {...}, "ts": 123, "error": null|{...}}
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    # system
    SYSTEM_HELLO = "system.hello"
    SYSTEM_HELLO_ACK = "system.hello_ack"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_SHUTDOWN = "system.shutdown"
    PING = "ping"
    PONG = "pong"
    LOG_MESSAGE = "log.message"
    ERROR = "error"


class ErrorPayload(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class Envelope(BaseModel):
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
    return make_message(
        type_,
        {"ok": False},
        id_=id_,
        error=ErrorPayload(code=code, message=message, detail=detail),
    )


def now_ms() -> int:
    return int(time.time() * 1000)
