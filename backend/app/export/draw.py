"""Draw detection overlays on BGR frames (server-side export)."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def format_label(obj: dict[str, Any], template: str = "{id}:{class}") -> str:
    display = obj.get("display_name") or obj.get("class_name") or ""
    return (
        template.replace("{id}", str(obj.get("id", "")))
        .replace("{class}", display)
        .replace("{confidence}", f"{float(obj.get('confidence') or 0) * 100:.0f}%")
        .replace("{track_id}", str(obj.get("track_id") if obj.get("track_id") is not None else "—"))
    )


def _hex_to_bgr(color: str, default=(237, 93, 76)) -> tuple[int, int, int]:
    try:
        c = color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return (b, g, r)
    except Exception:  # noqa: BLE001
        return default


def draw_objects(
    frame: np.ndarray,
    objects: list[dict[str, Any]],
    *,
    label_template: str = "{id}:{class}",
    scale: float = 1.0,
) -> np.ndarray:
    """In-place style draw. Skips visible=False. Assumes geom.bbox."""
    h, w = frame.shape[:2]
    for obj in objects:
        if obj.get("visible") is False:
            continue
        geom = obj.get("geom") or obj.get("geometry") or {}
        bbox = geom.get("bbox") if isinstance(geom, dict) else None
        if not bbox or len(bbox) < 4:
            continue
        x1, y1, x2, y2 = [float(v) for v in bbox[:4]]
        style = obj.get("style") or {}
        color = _hex_to_bgr(str(style.get("color") or "#2F6FED"))
        lw = max(1, int(style.get("line_width") or 2))

        p1 = (int(x1), int(y1))
        p2 = (int(x2), int(y2))
        cv2.rectangle(frame, p1, p2, color, lw)

        label = format_label(obj, label_template)
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55 * scale
        thickness = max(1, int(1 * scale))
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)
        ly = max(0, y1 - th - 8)
        cv2.rectangle(frame, (p1[0], int(ly)), (p1[0] + tw + 8, int(ly) + th + 8), color, -1)
        cv2.putText(
            frame,
            label,
            (p1[0] + 4, int(ly) + th + 2),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )
    return frame
