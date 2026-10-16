"""配置 Loguru 日志并把日志事件转发给 WebSocket 客户端。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from loguru import logger

# 移除 Loguru 默认 stderr 输出，再添加统一格式的终端 sink。
logger.remove()

# 保存当前已注册的 WebSocket 日志接收回调。
_ws_sinks: list[Callable[[dict], None]] = []


def broadcast_log(record: dict) -> None:
    """将结构化日志记录推送到当前 WebSocket 日志订阅者。

    Args:
        record: Loguru 捕获的结构化日志记录。
    """

    for sink in list(_ws_sinks):
        try:
            sink(record)
        except Exception:  # noqa: BLE001 - log fan-out must never break the app
            pass


def add_ws_sink(sink: Callable[[dict], None]) -> None:
    """注册一个接收日志事件的 WebSocket 回调。

    Args:
        sink: 接收结构化日志事件的回调函数。
    """

    _ws_sinks.append(sink)


def remove_ws_sink(sink: Callable[[dict], None]) -> None:
    """移除已注册的 WebSocket 日志回调。

    Args:
        sink: 接收结构化日志事件的回调函数。
    """

    if sink in _ws_sinks:
        _ws_sinks.remove(sink)


def _ws_sink(message) -> None:  # loguru Message
    """把 Loguru 记录转换为前端日志负载后广播。

    Args:
        message: 待发送或解析的协议消息。
    """

    record = message.record
    payload = {
        "level": record["level"].name,
        "message": record["message"],
        "logger": record["name"],
        "ts_text": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "extra": dict(record["extra"]),
    }
    broadcast_log(payload)


def setup_logging(logs_dir: Path, level: str = "INFO") -> None:
    """配置文件轮转、控制台输出和 WebSocket 日志转发。

    Args:
        logs_dir: 日志文件保存目录。
        level: 日志级别名称，例如 ``INFO`` 或 ``DEBUG``。
    """

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "yolo-vision-workbench_{time:YYYYMMDD}.log"

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )
    logger.add(
        log_file,
        level=level,
        rotation="00:00",
        retention="14 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    logger.add(_ws_sink, level=level)

    logger.info("logging initialized level={} dir={}", level, logs_dir)
