"""SQLite connection helpers. One project DB under projects/<name>/database.sqlite
or a workspace default DB for global (no-project) runs."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from loguru import logger

_SCHEMA = Path(__file__).with_name("schema.sql")
_LOCK = threading.RLock()
_CONN: sqlite3.Connection | None = None
_DB_PATH: Path | None = None


def db_path_for_project(projects_dir: Path, project_id: str = "default") -> Path:
    root = projects_dir / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root / "database.sqlite"


def connect(path: Path) -> sqlite3.Connection:
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
    with _LOCK:
        if _CONN is None:
            raise RuntimeError("database not connected")
        return _CONN


def migrate() -> None:
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
    global _CONN
    with _LOCK:
        if _CONN is not None:
            _CONN.close()
            _CONN = None


def reconnect(path: Path) -> sqlite3.Connection:
    """Switch to another project database (close previous first)."""
    close()
    return connect(path)


def current_path() -> Path | None:
    return _DB_PATH
