"""Task / result persistence DAO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.database.connection import get_conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_task(task: dict[str, Any]) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO tasks(
          task_id, type, status, progress, progress_detail_json, params_json,
          profile_id, session_id, project_id, error, error_code, result_ref,
          parent_task_id, created_at, updated_at, finished_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(task_id) DO UPDATE SET
          status=excluded.status,
          progress=excluded.progress,
          progress_detail_json=excluded.progress_detail_json,
          error=excluded.error,
          error_code=excluded.error_code,
          result_ref=excluded.result_ref,
          updated_at=excluded.updated_at,
          finished_at=excluded.finished_at
        """,
        (
            task["task_id"],
            task["type"],
            task["status"],
            task.get("progress", 0.0),
            json.dumps(task.get("progress_detail") or {}, ensure_ascii=False),
            json.dumps(task.get("params") or {}, ensure_ascii=False),
            task.get("profile_id"),
            task.get("session_id"),
            task.get("project_id"),
            task.get("error"),
            task.get("error_code"),
            task.get("result_ref"),
            task.get("parent_task_id"),
            task.get("created_at") or _now(),
            task.get("updated_at") or _now(),
            task.get("finished_at"),
        ),
    )
    conn.commit()


def list_tasks(limit: int = 100) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        item = dict(r)
        item["progress_detail"] = json.loads(item.pop("progress_detail_json") or "{}")
        item["params"] = json.loads(item.pop("params_json") or "{}")
        out.append(item)
    return out


def save_frame_result(
    task_id: str,
    frame: dict[str, Any],
    *,
    media_path: str | None = None,
) -> None:
    conn = get_conn()
    frame_id = int(frame.get("frame_id", 0))
    meta = frame.get("meta") or {}
    now = _now()

    media_id = None
    if media_path:
        media_id = f"m_{task_id}_{frame_id}"
        conn.execute(
            """
            INSERT OR REPLACE INTO media(media_id, task_id, kind, path, width, height, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (media_id, task_id, "image", media_path, None, None, now),
        )

    conn.execute(
        """
        INSERT OR REPLACE INTO frames(
          task_id, frame_id, media_id, infer_ms, pipeline_ms, is_detect_frame, meta_json, created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            task_id,
            frame_id,
            media_id,
            meta.get("infer_ms"),
            meta.get("pipeline_ms"),
            1,
            json.dumps(meta, ensure_ascii=False),
            now,
        ),
    )

    conn.execute("DELETE FROM objects WHERE task_id=? AND frame_id=?", (task_id, frame_id))
    for obj in frame.get("objects") or []:
        geom = obj.get("geom") or {}
        conn.execute(
            """
            INSERT INTO objects(
              task_id, frame_id, object_id, model_id, class_id, class_name, display_name,
              confidence, geom_type, geom_json, track_id, visible, style_json, extra_json,
              created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id,
                frame_id,
                int(obj.get("id", 0)),
                str(obj.get("model_id", "")),
                int(obj.get("class_id", -1)),
                str(obj.get("class_name", "")),
                obj.get("display_name"),
                float(obj.get("confidence", 0.0)),
                str(obj.get("geom_type", "bbox")),
                json.dumps(geom, ensure_ascii=False),
                obj.get("track_id"),
                1 if obj.get("visible", True) else 0,
                json.dumps(obj.get("style") or {}, ensure_ascii=False),
                json.dumps(obj.get("extra") or {}, ensure_ascii=False),
                now,
                now,
            ),
        )
    conn.commit()


def append_op(
    task_id: str,
    action: str,
    *,
    frame_id: int | None = None,
    target_type: str = "object",
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
    actor: str = "user",
) -> dict[str, Any]:
    conn = get_conn()
    now = _now()
    cur = conn.execute(
        """
        INSERT INTO ops(task_id, frame_id, action, target_type, target_id, payload_json, actor, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            task_id,
            frame_id,
            action,
            target_type,
            target_id,
            json.dumps(payload or {}, ensure_ascii=False),
            actor,
            now,
        ),
    )
    conn.commit()
    return {
        "op_id": cur.lastrowid,
        "task_id": task_id,
        "frame_id": frame_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "payload": payload or {},
        "actor": actor,
        "created_at": now,
    }


def list_ops(task_id: str, *, limit: int = 1000) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ops WHERE task_id=? ORDER BY op_id ASC LIMIT ?",
        (task_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        out.append(item)
    return out


def set_object_visible(
    task_id: str,
    frame_id: int,
    object_id: int,
    model_id: str,
    visible: bool,
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE objects SET visible=?, updated_at=?
        WHERE task_id=? AND frame_id=? AND object_id=? AND model_id=?
        """,
        (1 if visible else 0, _now(), task_id, frame_id, object_id, model_id),
    )
    conn.commit()
    return cur.rowcount


def set_object_style(
    task_id: str,
    frame_id: int,
    object_id: int,
    model_id: str,
    style: dict[str, Any],
) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        UPDATE objects SET style_json=?, updated_at=?
        WHERE task_id=? AND frame_id=? AND object_id=? AND model_id=?
        """,
        (json.dumps(style, ensure_ascii=False), _now(), task_id, frame_id, object_id, model_id),
    )
    conn.commit()
    return cur.rowcount
