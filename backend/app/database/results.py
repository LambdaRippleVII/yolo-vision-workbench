"""Query detection results stored in SQLite."""

from __future__ import annotations

import json
from typing import Any

from app.database.connection import get_conn


def list_task_frames(task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT f.frame_id, f.pipeline_ms, f.infer_ms, f.is_detect_frame, f.meta_json,
               COUNT(o.object_id) AS object_count
        FROM frames f
        LEFT JOIN objects o ON o.task_id = f.task_id AND o.frame_id = f.frame_id
        WHERE f.task_id = ?
        GROUP BY f.frame_id
        ORDER BY f.frame_id
        LIMIT ?
        """,
        (task_id, limit),
    ).fetchall()
    out = []
    for r in rows:
        meta = json.loads(r["meta_json"] or "{}")
        out.append(
            {
                "frame_id": int(r["frame_id"]),
                "object_count": int(r["object_count"] or 0),
                "pipeline_ms": r["pipeline_ms"],
                "is_detect_frame": bool(r["is_detect_frame"]),
                "is_detect": bool(meta.get("is_detect_frame", r["is_detect_frame"])),
            }
        )
    return out


def get_frame_objects(task_id: str, frame_id: int) -> dict[str, Any]:
    conn = get_conn()
    frame_row = conn.execute(
        "SELECT * FROM frames WHERE task_id=? AND frame_id=?",
        (task_id, frame_id),
    ).fetchone()
    obj_rows = conn.execute(
        """
        SELECT object_id, model_id, class_id, class_name, display_name, confidence,
               geom_type, geom_json, track_id, visible, style_json
        FROM objects WHERE task_id=? AND frame_id=?
        ORDER BY object_id
        """,
        (task_id, frame_id),
    ).fetchall()
    objects = []
    for r in obj_rows:
        objects.append(
            {
                "id": r["object_id"],
                "model_id": r["model_id"],
                "class_id": r["class_id"],
                "class_name": r["class_name"],
                "display_name": r["display_name"],
                "confidence": r["confidence"],
                "geom_type": r["geom_type"],
                "geom": json.loads(r["geom_json"] or "{}"),
                "track_id": r["track_id"],
                "visible": bool(r["visible"]),
                "style": json.loads(r["style_json"] or "{}"),
            }
        )
    return {
        "task_id": task_id,
        "frame_id": frame_id,
        "objects": objects,
        "found": frame_row is not None,
    }


def extract_video_frame_jpeg(video_path: str, frame_id: int, quality: int = 85) -> bytes | None:
    """Return JPEG bytes of a single video frame (for replay preview)."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = cap.read()
        if not ok:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return None
        return buf.tobytes()
    finally:
        cap.release()
