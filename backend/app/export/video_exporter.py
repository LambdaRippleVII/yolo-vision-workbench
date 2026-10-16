"""根据逐帧检测结果生成带标注的视频。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import cv2
from loguru import logger

from app.database.connection import get_conn
from app.export.draw import draw_objects
from app.utils.image_io import open_video_capture, video_open_error_message


def load_frame_objects(task_id: str) -> dict[int, list[dict[str, Any]]]:
    """从数据库读取任务对象，并按帧编号组织检测对象。

    Args:
        task_id: 任务的唯一标识。

    Returns:
        以帧编号为键、检测对象列表为值的映射。
    """

    conn = get_conn()
    rows = conn.execute(
        "SELECT frame_id, object_id, model_id, class_id, class_name, display_name, confidence, geom_type, geom_json, track_id, visible, style_json FROM objects WHERE task_id=? ORDER BY frame_id, object_id",
        (task_id,),
    ).fetchall()
    out: dict[int, list[dict[str, Any]]] = {}
    for r in rows:
        item = {
            "id": r["object_id"],
            "model_id": r["model_id"],
            "class_id": r["class_id"],
            "class_name": r["class_name"],
            "display_name": r["display_name"],
            "confidence": r["confidence"],
            "geom_type": r["geom_type"],
            "geom": __import__("json").loads(r["geom_json"] or "{}"),
            "track_id": r["track_id"],
            "visible": bool(r["visible"]),
            "style": __import__("json").loads(r["style_json"] or "{}"),
        }
        out.setdefault(int(r["frame_id"]), []).append(item)
    return out


def export_video(
    source_video: str | Path,
    output_path: str | Path,
    frame_objects: dict[int, list[dict[str, Any]]],
    *,
    label_template: str = "{id}:{class}",
    fps: float | None = None,
    hidden_classes: list[str] | None = None,
    progress_cb: Callable[[float], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """逐帧读取源视频，绘制检测结果并写出 MP4 文件。

    Args:
        source_video: 原始视频文件路径。
        output_path: 导出文件的目标路径。
        frame_objects: 按帧编号索引的检测对象集合。
        label_template: 用于拼接对象编号、类别和置信度的标签模板。
        fps: 输出视频的帧率。
        hidden_classes: 导出时需要隐藏的类别名称集合。
        progress_cb: 接收归一化任务进度的回调函数。
        cancel_cb: 返回是否已收到取消请求的回调函数。

    Returns:
        包含输出路径、处理帧数、标注帧数、帧率和尺寸的结果字典。

    Raises:
        FileNotFoundError: 源视频无法打开时抛出。
        RuntimeError: 输出视频写入器无法打开时抛出。
    """

    source_video = Path(source_video)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cap = open_video_capture(source_video)
    if not cap.isOpened():
        raise FileNotFoundError(video_open_error_message(source_video))

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    out_fps = fps if fps and fps > 0 else src_fps
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, out_fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"cannot open writer: {output_path}")

    frame_id = 0
    drawn = 0
    try:
        while True:
            if cancel_cb and cancel_cb():
                break
            ok, frame = cap.read()
            if not ok:
                break
            objs = frame_objects.get(frame_id) or []
            if hidden_classes:
                objs = [o for o in objs if o.get("class_name") not in set(hidden_classes)]
            if objs:
                draw_objects(frame, objs, label_template=label_template)
                drawn += 1
            writer.write(frame)
            frame_id += 1
            if progress_cb and total:
                progress_cb(min(1.0, frame_id / total))
    finally:
        cap.release()
        writer.release()

    logger.info("export done frames={} drawn={} out={}", frame_id, drawn, output_path)
    return {
        "output_path": str(output_path),
        "frames": frame_id,
        "drawn_frames": drawn,
        "fps": out_fps,
        "width": width,
        "height": height,
    }
