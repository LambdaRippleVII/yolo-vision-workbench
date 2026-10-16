"""处理本地媒体目录与图像清单查询请求。"""

from __future__ import annotations

from typing import Any

from app.utils.image_io import imread_unicode
from app.utils.media_list import list_folder_images
from app.websocket.protocol import make_error, make_message
from app.websocket.server import ConnectionContext, WebSocketHub


def register_media_handlers(hub: WebSocketHub) -> None:
    """注册本地媒体目录扫描消息处理器。

    Args:
        hub: 管理 WebSocket 连接及处理器的服务实例。
    """

    async def on_list_folder(msg: dict[str, Any], ctx: ConnectionContext) -> dict[str, Any]:
        data = msg.get("data") or {}
        folder = data.get("folder_path")
        if not folder:
            return make_error("media.listFolder", "BAD_REQUEST", "folder_path required", id_=msg.get("id"))
        try:
            items = list_folder_images(str(folder), recursive=bool(data.get("recursive")))
        except Exception as exc:  # noqa: BLE001
            return make_error("media.listFolder", "INTERNAL", str(exc), id_=msg.get("id"))

        # 附带缩略图，让前端相册可以立即绘制列表。
        thumbs: list[dict[str, Any]] = []
        want_thumb = bool(data.get("with_thumbs", True))
        for it in items:
            entry = dict(it)
            if want_thumb:
                import base64

                img = imread_unicode(it["path"])
                if img is not None:
                    try:
                        import cv2

                        h, w = img.shape[:2]
                        scale = min(1.0, 160 / max(h, w))
                        if scale < 1.0:
                            img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))))
                        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        if ok:
                            b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                            entry["thumb_url"] = f"data:image/jpeg;base64,{b64}"
                    except Exception:  # noqa: BLE001
                        pass
            thumbs.append(entry)

        return make_message(
            "media.listFolder",
            {"ok": True, "folder_path": str(folder), "items": thumbs, "count": len(thumbs)},
            id_=msg.get("id"),
        )

    hub.register("media.listFolder", on_list_folder)
