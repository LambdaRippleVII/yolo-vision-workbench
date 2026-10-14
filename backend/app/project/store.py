"""Project directory + project.json store."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from app.database.connection import db_path_for_project, migrate, reconnect

_SAFE_NAME = re.compile(r"^[\w\u4e00-\u9fff][\w\u4e00-\u9fff .-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.current_id: str = "default"

    def _root(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def _meta_path(self, project_id: str) -> Path:
        return self._root(project_id) / "project.json"

    def list_projects(self) -> list[dict[str, Any]]:
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
                # still list folder-only (e.g. default)
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
        # current first
        items.sort(key=lambda x: (0 if x.get("project_id") == self.current_id else 1, x.get("name") or ""))
        return items

    def create(self, name: str, description: str = "") -> dict[str, Any]:
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
