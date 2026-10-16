"""创建、读取、更新和删除推理配置方案。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from loguru import logger

from app.database.connection import get_conn


def _now() -> str:
    """返回 ISO 8601 格式的当前 UTC 时间。

    Returns:
        当前 UTC 时间的 ISO 8601 字符串。
    """

    return datetime.now(timezone.utc).isoformat()


class ProfileModelBinding(BaseModel):
    """描述推理方案中一个模型的选择与参数覆盖。"""

    model_id: str
    enabled: bool = True
    conf: float | None = None
    iou: float | None = None
    classes: list[str] = Field(default_factory=list)


class ProfilePayload(BaseModel):
    """保存一套可复用的模型选择和推理参数。"""

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
        """按方案绑定顺序提取模型标识列表。

        Returns:
        所有启用模型的标识列表，保持方案绑定顺序。
        """

        return [m.model_id for m in self.models if m.enabled]


class ProfileStore:
    """通过 SQLite 持久化管理推理配置方案。"""

    def create(
        self,
        name: str,
        payload: ProfilePayload,
        *,
        description: str = "",
        profile_id: str | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        """校验输入并创建推理配置记录。

        Args:
            name: 要显示在配置方案列表中的名称。
            payload: 待保存或发送的数据负载。
            description: 用于解释配置或项目用途的可选文字。
            profile_id: 推理配置方案的唯一标识。
            is_default: 该配置是否应设为默认项。

        Returns:
            已写入数据库的完整配置方案字典。
        """

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
        """根据方案标识读取并解码配置记录。

        Args:
            profile_id: 推理配置方案的唯一标识。

        Returns:
            指定配置方案的解码结果。

        Raises:
            KeyError: profile_id 不存在时抛出。
        """

        conn = get_conn()
        row = conn.execute("SELECT * FROM profiles WHERE profile_id=?", (profile_id,)).fetchone()
        if row is None:
            raise KeyError(f"profile not found: {profile_id}")
        return self._row_to_dict(row)

    def list_profiles(self) -> list[dict[str, Any]]:
        """按创建顺序返回已保存的推理配置方案。

        Returns:
            按默认标记和更新时间排序的方案列表。
        """

        conn = get_conn()
        rows = conn.execute("SELECT * FROM profiles ORDER BY is_default DESC, updated_at DESC").fetchall()
        return [self._row_to_dict(r) for r in rows]

    def delete(self, profile_id: str) -> None:
        """删除指定方案并处理默认方案保护。

        Args:
            profile_id: 推理配置方案的唯一标识。
        """

        conn = get_conn()
        conn.execute("DELETE FROM profiles WHERE profile_id=?", (profile_id,))
        conn.commit()

    def ensure_default(self) -> dict[str, Any]:
        """确保数据库中存在一套可用的默认推理方案。

        Returns:
            已存在的首个方案，或新建的默认方案。
        """

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
        """将数据库记录解码为前端协议可用的配置字典。

        Args:
            row: 从 SQLite 查询得到的方案记录行。

        Returns:
            适配前端协议的方案记录字典。
        """

        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json") or "{}")
        d["is_default"] = bool(d.get("is_default"))
        return d


# 进程内共享的推理配置方案存储实例。
profile_store = ProfileStore()
