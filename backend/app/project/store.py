"""管理项目目录、元数据和当前项目状态。"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.database.connection import db_path_for_project, migrate, reconnect

# 限制项目目录名称字符和长度的正则表达式。
_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff][\w\u4e00-\u9fff .-]{0,63}$")


def _now() -> str:
    """返回 ISO 8601 格式的当前 UTC 时间。

    Returns:
        当前 UTC 时间的 ISO 8601 字符串。
    """

    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    """管理项目元数据、目录结构和当前打开项目。"""

    def __init__(self, projects_dir: Path) -> None:
        """初始化项目根目录并准备默认项目。

        Args:
            projects_dir: 项目数据的根目录。
        """

        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.current_id: str = "default"

    def _root(self, project_id: str) -> Path:
        """根据项目标识返回并校验对应的数据目录。

        Args:
            project_id: 项目的唯一标识。

        Returns:
            指定项目的数据根目录路径。
        """

        return self.projects_dir / project_id

    def _meta_path(self, project_id: str) -> Path:
        """返回指定项目的元数据文件路径。

        Args:
            project_id: 项目的唯一标识。

        Returns:
            指定项目的 project.json 文件路径。
        """

        return self._root(project_id) / "project.json"

    def list_projects(self) -> list[dict[str, Any]]:
        """读取所有项目元数据并返回项目列表。

        Returns:
            所有项目的公开元数据列表，当前项目排在首位。
        """

        items: list[dict[str, Any]] = []
        if not self.projects_dir.exists():
            return items
        for p in sorted(self.projects_dir.iterdir()):
            if not p.is_dir():
                continue
            meta_file = p / "project.json"
            if meta_file.exists():
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                items.append(data)
            else:
        # 即使没有元数据文件，也保留仅存在目录的项目（例如 default）。
                items.append(
                    {
                        "project_id": p.name,
                        "name": p.name,
                        "root_path": str(p),
                        "created_at": None,
                        "updated_at": None,
                        "description": "",
                    }
                )
        # 当前项目始终排在列表第一项。
        items.sort(key=lambda x: (0 if x.get("project_id") == self.current_id else 1, x.get("name") or ""))
        return items

    def create(self, name: str, description: str = "") -> dict[str, Any]:
        """执行与create相关的处理逻辑。

        Args:
            name: 新项目的显示名称。
            description: 用于解释配置或项目用途的可选文字。

        Returns:
            新建项目的元数据字典。

        Raises:
            ValueError: 项目名称不符合允许字符规则时抛出。
        """

        name = (name or "").strip()
        if not _SAFE_NAME.match(name):
            raise ValueError("项目名称仅支持中英文、数字、空格、点、连字符")
        project_id = name if not (self._root(name).exists() and (self._root(name) / "project.json").exists()) else f"{name}_{uuid.uuid4().hex[:6]}"
        root = self._root(project_id)
        for sub in ("images", "videos", "models", "results", "profiles"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        meta = {
            "project_id": project_id,
            "name": name,
            "root_path": str(root),
            "created_at": _now(),
            "updated_at": _now(),
            "description": description,
            "version": 1,
            "last_task_id": None,
        }
        self._meta_path(project_id).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("project created {}", project_id)
        return meta

    def open(self, project_id: str) -> dict[str, Any]:
        """切换当前项目并返回其持久化元数据。

        Args:
            project_id: 项目的唯一标识。

        Returns:
            切换后的项目元数据字典。

        Raises:
            FileNotFoundError: project_id 对应目录不存在时抛出。
        """

        root = self._root(project_id)
        if not root.exists():
            raise FileNotFoundError(f"project not found: {project_id}")
        for sub in ("images", "videos", "models", "results", "profiles"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        db_path = db_path_for_project(self.projects_dir, project_id)
        reconnect(db_path)
        migrate()
        self.current_id = project_id

        meta_file = self._meta_path(project_id)
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        else:
            meta = {
                "project_id": project_id,
                "name": project_id,
                "root_path": str(root),
                "created_at": _now(),
                "updated_at": _now(),
                "description": "",
                "version": 1,
            }
            meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        meta["updated_at"] = _now()
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("project opened {}", project_id)
        return meta

    def current(self) -> dict[str, Any]:
        """返回当前打开的项目及其公开状态。

        Returns:
            当前项目的持久化元数据；不存在元数据文件时返回基本信息。
        """

        root = self._root(self.current_id)
        meta_file = self._meta_path(self.current_id)
        if meta_file.exists():
            return json.loads(meta_file.read_text(encoding="utf-8"))
        return {
            "project_id": self.current_id,
            "name": self.current_id,
            "root_path": str(root),
        }

    def save_meta(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """将项目元数据补丁合并后安全写回磁盘。

        Args:
            project_id: 项目的唯一标识。
            patch: 要合并写入项目元数据的字段补丁。

        Returns:
            合并补丁并更新后的项目元数据字典。
        """

        meta_file = self._meta_path(project_id)
        meta = {}
        if meta_file.exists():
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        meta.update(patch)
        meta["project_id"] = project_id
        meta["updated_at"] = _now()
        meta_file.parent.mkdir(parents=True, exist_ok=True)
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta
