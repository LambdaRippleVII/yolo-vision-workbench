"""Inference Profile: named parameter presets for a project."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from loguru import logger

from app.database.connection import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProfileModelBinding(BaseModel):
    model_id: str
    enabled: bool = True
    conf: float | None = None
    iou: float | None = None
    classes: list[str] = Field(default_factory=list)


class ProfilePayload(BaseModel):
    models: list[ProfileModelBinding] = Field(default_factory=list)
    pipeline: dict[str, Any] = Field(default_factory=lambda: {"mode": "parallel", "merge": "concat"})
    runtime: dict[str, Any] = Field(
        default_factory=lambda: {
            "device": "cpu",
            "skip_frame": 5,
            "box_persistence": 5,
        }
    )
    render: dict[str, Any] = Field(
        default_factory=lambda: {
            "label_template": "{id}:{class}",
            "default_color": "#2F6FED",
            "line_width": 2,
            "show_confidence": True,
        }
    )
    export: dict[str, Any] = Field(default_factory=dict)

    def model_ids(self) -> list[str]:
        return [m.model_id for m in self.models if m.enabled]


class ProfileStore:
    def create(
        self,
        name: str,
        payload: ProfilePayload,
        *,
        description: str = "",
        profile_id: str | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        pid = profile_id or f"p_{uuid.uuid4().hex[:10]}"
        now = _now()
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO profiles(profile_id, name, description, payload_json, is_default, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(profile_id) DO UPDATE SET
              name=excluded.name,
              description=excluded.description,
              payload_json=excluded.payload_json,
              is_default=excluded.is_default,
              updated_at=excluded.updated_at
            """,
            (
                pid,
                name,
                description,
                payload.model_dump_json(),
                1 if is_default else 0,
                now,
                now,
            ),
        )
        conn.commit()
        logger.info("profile saved {}", pid)
        return self.get(pid)

    def get(self, profile_id: str) -> dict[str, Any]:
        conn = get_conn()
        row = conn.execute("SELECT * FROM profiles WHERE profile_id=?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(f"profile not found: {profile_id}")
        return self._row_to_dict(row)

    def list_profiles(self) -> list[dict[str, Any]]:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM profiles ORDER BY is_default DESC, updated_at DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, profile_id: str) -> None:
        conn = get_conn()
        conn.execute("DELETE FROM profiles WHERE profile_id=?", (profile_id,))
        conn.commit()

    def ensure_default(self) -> dict[str, Any]:
        try:
            items = self.list_profiles()
            if items:
                return items[0]
        except Exception:  # noqa: BLE001
            pass
        payload = ProfilePayload(
            models=[
                ProfileModelBinding(model_id="demo", enabled=True, conf=0.45),
            ]
        )
        return self.create("默认配置", payload, description="工作台默认推理参数", profile_id="default", is_default=True)

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json") or "{}")
        d["is_default"] = bool(d.get("is_default"))
        return d


profile_store = ProfileStore()
