"""FastAPI application entry. Assembly only — no business logic here."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import load_config
from app.database import connect as db_connect
from app.database import db_path_for_project, migrate
from app.model_manager.loader import ModelManager
from app.project.store import ProjectStore
from app.task.manager import TaskManager
from app.utils.logging import setup_logging
from app.websocket.handlers import (
    register_camera_handlers,
    register_detect_handlers,
    register_export_image_handlers,
    register_media_handlers,
    register_model_handlers,
    register_ops_handlers,
    register_profile_handlers,
    register_project_handlers,
    register_result_handlers,
    register_system_handlers,
    register_task_handlers,
    register_video_handlers,
)
from app.websocket.protocol import make_message
from app.websocket.server import WebSocketHub

config = load_config()
setup_logging(config.logs_dir, config.log_level)

hub = WebSocketHub(config)
model_manager = ModelManager(config.models_dir, config.models_dir / "repository")
task_manager = TaskManager(model_manager)


def _task_event(payload: dict) -> None:
    """Forward task events to all WS clients from worker threads."""
    event = payload.get("event", "progress")
    type_map = {
        "created": "task.progress",
        "progress": "task.progress",
        "done": "task.done",
        "cancelled": "task.done",
    }
    msg_type = type_map.get(event, "task.progress")
    message = make_message(msg_type, payload)
    loop = getattr(hub, "_loop", None)
    if loop and not loop.is_closed():
        asyncio.run_coroutine_threadsafe(hub.broadcast(message), loop)


task_manager.on_event(_task_event)

# SQLite workspace DB (default project). Per-project DBs switch later via project.open.
db_connect(db_path_for_project(config.projects_dir, "default"))
migrate()

project_store = ProjectStore(config.projects_dir)
project_store.current_id = "default"

register_system_handlers(hub, config)
register_model_handlers(hub, model_manager)
register_detect_handlers(hub, task_manager)
register_task_handlers(hub, task_manager)
register_profile_handlers(hub)
register_project_handlers(hub, project_store)
register_video_handlers(hub, task_manager)
register_result_handlers(hub)
register_ops_handlers(hub)
register_camera_handlers(hub, model_manager, task_manager)
register_export_image_handlers(hub)
register_media_handlers(hub)

try:
    from app.project.profile import profile_store

    profile_store.ensure_default()
except Exception as exc:  # noqa: BLE001
    logger.warning("ensure default profile failed: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.bind_loop(asyncio.get_running_loop())
    logger.info(
        "backend starting host={} port={} root={}",
        config.host,
        config.port,
        config.root,
    )
    yield
    logger.info("backend shutdown")


app = FastAPI(
    title="YOLO Vision Workbench Backend",
    version=config.app_version,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/media")
async def media(path: str):
    """Serve local media for <video>/<img> preview (file:// is unreliable)."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from app.utils import media_http

    resolved = media_http.resolve_media_path(path, [config.root, config.projects_dir])
    if resolved is None:
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(
        resolved,
        media_type=media_http.guess_media_type(resolved),
    )


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ready",
        "version": config.app_version,
        "pid": os.getpid(),
        "protocol_version": config.protocol_version,
        "product": "YOLO Vision Workbench",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await hub.handle_connection(websocket)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    main()
