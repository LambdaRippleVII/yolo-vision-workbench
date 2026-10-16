"""读取环境变量并初始化服务地址、日志、模型和项目目录。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_root() -> Path:
    """根据环境覆盖项解析后端使用的应用根目录。

    Returns:
        解析后的应用根目录绝对路径。
    """

    env = os.environ.get("YOLO_STUDIO_ROOT")
    if env:
        return Path(env).resolve()
    # 当前文件位于 backend/app，向上两级即可回到仓库根目录。
    return Path(__file__).resolve().parents[2]


def _int_env(name: str, default: int) -> int:
    """读取整型环境变量，并在未设置或格式无效时使用默认值。

    Args:
        name: 要读取的环境变量名称。
        default: 缺省值；配置项缺失或无法解析时使用该值。

    Returns:
        环境变量中的整数值；未设置或无法解析时返回 default。
    """

    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class AppConfig:
    """保存服务地址、版本号以及日志、模型和项目存储目录。"""

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
        """返回 WebSocket 服务使用的路由路径。

        Returns:
            WebSocket 路由路径，固定为 ``/ws``。
        """

        return "/ws"

    @property
    def ws_url(self) -> str:
        """根据当前主机和端口拼接 WebSocket 服务地址。

        Returns:
            根据当前主机、端口和路由路径拼接的 WebSocket 地址。
        """

        return f"ws://{self.host}:{self.port}{self.ws_path}"


def load_config() -> AppConfig:
    """读取环境变量、创建数据目录并生成不可变的应用配置。

    Returns:
        含服务地址和存储目录的不可变应用配置。
    """

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
