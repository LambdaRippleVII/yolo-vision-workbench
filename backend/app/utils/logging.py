"""loguru setup: file sink + optional WebSocket broadcast sink."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

from loguru import logger

# Remove default stderr sink; we re-add a clean one.
logger.remove()

_ws_sinks: list[Callable[[dict], None]] = []


def broadcast_log(record: dict) -> None:
    for sink in list(_ws_sinks):
        try:
            sink(record)
        except Exception:  # noqa: BLE001 - log fan-out must never break the app
            pass


def add_ws_sink(sink: Callable[[dict], None]) -> None:
    _ws_sinks.append(sink)


def remove_ws_sink(sink: Callable[[dict], None]) -> None:
    if sink in _ws_sinks:
        _ws_sinks.remove(sink)


def _ws_sink(message) -> None:  # loguru Message
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
