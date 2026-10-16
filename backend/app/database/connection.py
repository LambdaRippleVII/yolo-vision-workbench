"""管理 SQLite 连接、项目数据库切换和表结构迁移。"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from loguru import logger

# 当前后端使用的 SQLite 建表脚本路径。
_SCHEMA = Path(__file__).with_name("schema.sql")
# 保护全局数据库连接状态的可重入锁。
_LOCK = threading.RLock()
# 当前进程持有的 SQLite 数据库连接。
_CONN: sqlite3.Connection | None = None
# 当前连接所指向的 SQLite 文件路径。
_DB_PATH: Path | None = None


def db_path_for_project(projects_dir: Path, project_id: str = "default") -> Path:
    """创建项目数据目录并返回该项目的 SQLite 文件路径。

    Args:
        projects_dir: 项目数据的根目录。
        project_id: 项目的唯一标识。

    Returns:
        项目数据库的文件路径。
    """

    root = projects_dir / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root / "database.sqlite"


def connect(path: Path) -> sqlite3.Connection:
    """打开 SQLite 数据库并更新当前进程的共享连接。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        已启用 WAL、外键和忙等待设置的 SQLite 连接。
    """

    global _CONN, _DB_PATH
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        _CONN = conn
        _DB_PATH = path
        logger.info("sqlite connected {}", path)
        return conn


def get_conn() -> sqlite3.Connection:
    """返回当前项目数据库连接。

    Returns:
        由 connect 创建或 reconnect 恢复的 SQLite 连接。

    Raises:
        RuntimeError: 尚未建立数据库连接时抛出。
    """

    with _LOCK:
        if _CONN is None:
            raise RuntimeError("database not connected")
        return _CONN


def migrate() -> None:
    """读取建表脚本并在当前数据库中应用结构迁移。"""

    conn = get_conn()
    script = _SCHEMA.read_text(encoding="utf-8")
    with _LOCK:
        conn.executescript(script)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version INTEGER PRIMARY KEY,
              name TEXT NOT NULL,
              applied_at TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
        if not row or row["v"] is None:
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, '0001_init', datetime('now'))"
            )
        conn.commit()
    logger.info("database migrated")


def close() -> None:
    """关闭当前 SQLite 连接并清空共享连接状态。"""

    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close()
            _CONN = None


def reconnect(path: Path) -> sqlite3.Connection:
    """关闭旧连接，并连接到指定项目数据库。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        新建并配置完成的 SQLite 连接。
    """
    close()
    return connect(path)


def current_path() -> Path | None:
    """返回当前共享数据库连接对应的文件路径。

    Returns:
        当前数据库路径；尚未连接时返回 None。
    """

    return _DB_PATH
