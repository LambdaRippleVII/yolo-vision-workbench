"""组装 FastAPI 服务、注册消息处理器并管理服务生命周期。"""

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

# 后端启动时读取并固定使用的应用配置。
config = load_config()
# 按应用配置初始化日志，再构造服务组件，确保启动阶段的诊断信息可追踪。
setup_logging(config.logs_dir, config.log_level)

# 后端 WebSocket 连接与消息处理中心。
hub = WebSocketHub(config)
# 负责扫描、导入、加载和卸载模型的全局管理器。
model_manager = ModelManager(config.models_dir, config.models_dir / "repository")
# 负责创建、调度和跟踪推理任务的全局管理器。
task_manager = TaskManager(model_manager)


def _task_event(payload: dict) -> None:
    """将工作线程发出的任务事件安全投递到 WebSocket 事件循环。

    Args:
        payload: 待保存或发送的数据负载。
    """
    # 将任务生命周期事件映射到前端约定的消息类型。
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

# 启动时连接默认项目数据库；切换项目时由 project.open 更新当前连接。
db_connect(db_path_for_project(config.projects_dir, "default"))
migrate()

# 负责项目目录和当前项目信息的存储实例。
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
    """绑定异步事件循环并记录服务启动和关闭过程。

    Args:
        app: 正在启动或关闭的 FastAPI 应用实例。
    """

    hub.bind_loop(asyncio.get_running_loop())
    logger.info(
        "backend starting host={} port={} root={}",
        config.host,
        config.port,
        config.root,
    )
    yield
    logger.info("backend shutdown")


# 供 Uvicorn 启动并注册 HTTP 与 WebSocket 路由的 FastAPI 应用。
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


@app.api_route("/media", methods=["GET", "HEAD"])
async def media(path: str):
    """校验媒体文件路径后返回供前端预览的本地文件响应。

    Args:
        path: 待读取、写入或检查的文件系统路径。

    Returns:
        指向校验通过媒体文件的 FastAPI 文件响应。

    Raises:
        HTTPException: 媒体路径不存在或不在允许的根目录内时返回 404。
    """
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
    """返回服务就绪状态、版本和协议标识。

    Returns:
        包含就绪状态、应用版本、进程号、协议版本和产品标识的字典。
    """

    return {
        "status": "ready",
        "version": config.app_version,
        "pid": os.getpid(),
        "protocol_version": config.protocol_version,
        "product": "YOLO Vision Workbench",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """把新连接交由 WebSocketHub 执行生命周期管理。

    Args:
        websocket: 当前客户端的 WebSocket 连接对象。
    """

    await hub.handle_connection(websocket)


def main() -> None:
    """启动当前模块提供的命令行流程。"""

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
