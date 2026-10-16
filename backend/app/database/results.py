"""查询持久化的检测结果并提取视频预览帧。"""

from __future__ import annotations

import json
from typing import Any

from app.database.connection import get_conn
from app.utils.image_io import open_video_capture


def list_task_frames(task_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    """读取任务的帧索引、检测对象数量和推理元信息。

    Args:
        task_id: 任务的唯一标识。
        limit: 本次查询或保存允许处理的最大条目数。

    Returns:
        按帧号升序排列的帧摘要列表，最多包含 limit 条记录。
    """

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
    """读取指定帧及其全部检测对象，并整理为前端使用的结构。

    Args:
        task_id: 任务的唯一标识。
        frame_id: 视频帧的零基索引。

    Returns:
        包含任务号、帧号、对象清单和帧是否存在的字典。
    """

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
    """解码指定视频帧并编码为 JPEG 字节。

    Args:
        video_path: 视频文件路径。
        frame_id: 视频帧的零基索引。
        quality: JPEG 编码质量。

    Returns:
        JPEG 图像字节；视频或帧无法读取时返回 None。
    """
    import cv2

    cap = open_video_capture(video_path)
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
