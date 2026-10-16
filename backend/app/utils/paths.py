"""解析应用路径并确保目标目录存在。"""

from __future__ import annotations

from pathlib import Path

from app.config import AppConfig


def resolve_under_root(cfg: AppConfig, maybe_relative: str | Path) -> Path:
    """把相对路径限制在应用根目录下并解析为绝对路径。

    Args:
        cfg: 当前模型的解析后配置。
        maybe_relative: 待解析的绝对路径或相对路径。

    Returns:
        限制在 root 下的绝对路径；路径越界时抛出 ValueError。
    """
    p = Path(maybe_relative)
    if p.is_absolute():
        return p.resolve()
    return (cfg.root / p).resolve()


def ensure_dir(path: Path) -> Path:
    """创建目标目录并返回目录路径。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        已创建的目录路径。
    """

    path.mkdir(parents=True, exist_ok=True)
    return path
