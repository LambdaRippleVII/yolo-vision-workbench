"""Save annotated image / batch frames from results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
from loguru import logger

from app.database import results as results_db
from app.export.draw import draw_objects
from app.utils.image_io import (
    imread_unicode,
    imwrite_unicode,
    open_video_capture,
    video_open_error_message,
)


def save_annotated_image(
    source_image: str | Path,
    output_path: str | Path,
    objects: list[dict[str, Any]] | None = None,
    *,
    label_template: str = "{id}:{class}",
    include_source: bool = True,
) -> dict[str, Any]:
    """Draw objects onto image and save. Also write sidecar JSON."""
    source_image = Path(source_image)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = imread_unicode(source_image)
    if img is None:
        raise FileNotFoundError(f"cannot read image: {source_image}")

    objs = objects or []
    draw_objects(img, objs, label_template=label_template)
    imwrite_unicode(output_path, img)

    json_path = output_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "source": str(source_image),
                "output": str(output_path),
                "objects": objs,
                "label_template": label_template,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("saved annotated image {}", output_path)
    return {
        "output_path": str(output_path),
        "json_path": str(json_path),
        "object_count": len(objs),
    }


def save_frame_images(
    task_id: str,
    video_path: str | Path,
    output_dir: str | Path,
    frame_ids: list[int],
    *,
    label_template: str = "{id}:{class}",
    use_db_visible: bool = True,
) -> dict[str, Any]:
    """Export selected video frames as annotated stills."""
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = open_video_capture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(video_open_error_message(video_path))

    saved: list[str] = []
    try:
        for fid in sorted(set(int(x) for x in frame_ids)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fid)
            ok, frame = cap.read()
            if not ok:
                logger.warning("cannot read frame {}", fid)
                continue
            frame_result = results_db.get_frame_objects(task_id, fid)
            objs = frame_result.get("objects") or []
            draw_objects(frame, objs, label_template=label_template)
            out = output_dir / f"{video_path.stem}_f{fid:06d}.jpg"
            imwrite_unicode(out, frame)
            saved.append(str(out))
    finally:
        cap.release()

    return {"saved": saved, "count": len(saved)}
