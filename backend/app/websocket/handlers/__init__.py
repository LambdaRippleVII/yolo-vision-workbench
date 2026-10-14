"""WebSocket handlers package."""

from app.websocket.handlers.camera import register_camera_handlers
from app.websocket.handlers.detect import register_detect_handlers
from app.websocket.handlers.export_image import register_export_image_handlers
from app.websocket.handlers.media import register_media_handlers
from app.websocket.handlers.model import register_model_handlers
from app.websocket.handlers.ops import register_ops_handlers
from app.websocket.handlers.profile import register_profile_handlers
from app.websocket.handlers.project import register_project_handlers
from app.websocket.handlers.result import register_result_handlers
from app.websocket.handlers.system import register_system_handlers
from app.websocket.handlers.task import register_task_handlers
from app.websocket.handlers.video import register_video_handlers

__all__ = [
    "register_system_handlers",
    "register_model_handlers",
    "register_detect_handlers",
    "register_task_handlers",
    "register_profile_handlers",
    "register_project_handlers",
    "register_video_handlers",
    "register_result_handlers",
    "register_ops_handlers",
    "register_camera_handlers",
    "register_export_image_handlers",
    "register_media_handlers",
]
