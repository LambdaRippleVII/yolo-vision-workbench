"""Application configuration. Paths and ports are never hardcoded in business code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_root() -> Path:
    env = os.environ.get("YOLO_STUDIO_ROOT")
    if env:
        return Path(env).resolve()
    # backend/app/config.py -> backend/app -> backend -> repo root
    return Path(__file__).resolve().parents[2]


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    root: Path
    host: str
    port: int
    log_level: str
    logs_dir: Path
    models_dir: Path
    projects_dir: Path
    protocol_version: int = 1
    app_version: str = "0.2.5"

    @property
    def ws_path(self) -> str:
        return "/ws"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}{self.ws_path}"


def load_config() -> AppConfig:
    root = _default_root()
    host = os.environ.get("YOLO_STUDIO_HOST", "127.0.0.1")
    port = _int_env("YOLO_STUDIO_PORT", 8765)
    log_level = os.environ.get("YOLO_STUDIO_LOG_LEVEL", "INFO").upper()

    logs_dir = Path(os.environ.get("YOLO_STUDIO_LOGS_DIR", root / "logs")).resolve()
    models_dir = Path(os.environ.get("YOLO_STUDIO_MODELS_DIR", root / "models")).resolve()
    projects_dir = Path(
        os.environ.get("YOLO_STUDIO_PROJECTS_DIR", root / "projects")
    ).resolve()

    logs_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)

    return AppConfig(
        root=root,
        host=host,
        port=port,
        log_level=log_level,
        logs_dir=logs_dir,
        models_dir=models_dir,
        projects_dir=projects_dir,
    )
