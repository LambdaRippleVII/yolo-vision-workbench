"""创建、调度、取消并汇报图像、文件夹、视频和导出任务。"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from app.database import dao
from app.inference.pipeline import pipeline_engine
from app.inference.session import InferenceSession
from app.task.base import Task, TaskStatus, TaskType
from app.utils.image_io import open_video_capture, video_open_error_message

# 统一描述任务进度通知回调的函数签名。
ProgressCB = Callable[[dict[str, Any]], None]


class TaskManager:
    """协调任务创建、推理运行、进度通知和取消处理。"""

    def __init__(self, model_manager: Any) -> None:
        """初始化任务表、线程池和推理会话。

        Args:
            model_manager: 负责查询和加载模型的管理器。
        """

        self._model_manager = model_manager
        self._tasks: dict[str, Task] = {}
        self._lock = threading.RLock()
        self._listeners: list[ProgressCB] = []
        self._threads: dict[str, threading.Thread] = {}

    def on_event(self, cb: ProgressCB) -> None:
        """注册任务进度和完成事件的回调函数。

        Args:
            cb: 用于接收进度或结果的回调函数。
        """

        self._listeners.append(cb)

    def _emit(self, event: str, task: Task, **extra: Any) -> None:
        """将任务事件规范化后分发给注册的回调。

        Args:
            event: 任务生命周期事件名称。
            task: 需要广播生命周期事件的任务对象。
            **extra: 要附加到事件负载中的进度或错误字段。
        """

        payload = {"event": event, **task.to_dict(), **extra}
        try:
            dao.upsert_task(task.to_dict())
        except Exception as exc:  # noqa: BLE001
            logger.warning("persist task failed: {}", exc)
        for cb in list(self._listeners):
            try:
                cb(payload)
            except Exception as exc:  # noqa: BLE001
                logger.warning("task listener error: {}", exc)

    def get(self, task_id: str) -> Task | None:
        """按任务标识读取内存中的任务对象。

        Args:
            task_id: 任务的唯一标识。

        Returns:
            找到的任务对象；不存在时返回 None。
        """

        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        """按创建时间倒序返回当前进程中的任务快照。

        Returns:
            可序列化的任务字典列表。
        """

        with self._lock:
            return [t.to_dict() for t in sorted(self._tasks.values(), key=lambda x: x.created_at, reverse=True)]

    def create_image_task(
        self,
        media_path: str,
        model_ids: list[str],
        *,
        overrides: dict[str, Any] | None = None,
    ) -> Task:
        """构造单张图片推理任务并保存其输入参数。

        Args:
            media_path: 输入媒体文件路径。
            model_ids: 本次操作涉及的模型标识列表。
            overrides: 单图推理的置信度、类别筛选和尺寸覆盖项。

        Returns:
            已登记的单图推理任务。
        """

        task = Task(
            type=TaskType.IMAGE,
            params={"media_path": media_path, "overrides": overrides or {}},
            model_ids=list(model_ids),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def create_folder_task(
        self,
        folder_path: str,
        model_ids: list[str],
        *,
        overrides: dict[str, Any] | None = None,
        file_paths: list[str] | None = None,
    ) -> Task:
        """构造目录图片推理任务并记录待处理文件清单。

        Args:
            folder_path: 待扫描或处理的文件夹路径。
            model_ids: 本次操作涉及的模型标识列表。
            overrides: 批量推理的置信度、类别筛选和尺寸覆盖项。
            file_paths: 要处理的图片文件路径列表。

        Returns:
            已登记的目录批量推理任务。
        """

        task = Task(
            type=TaskType.FOLDER,
            params={
                "folder_path": folder_path,
                "overrides": overrides or {},
                "file_paths": list(file_paths or []),
            },
            model_ids=list(model_ids),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def cancel(self, task_id: str) -> Task:
        """请求取消指定任务并更新其生命周期状态。

        Args:
            task_id: 任务的唯一标识。

        Returns:
            已写入取消请求后的任务对象。
        """

        with self._lock:
            task = self._tasks[task_id]
            task.request_cancel()
            if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.PAUSED):
                if task.status == TaskStatus.PENDING:
                    task.transition(TaskStatus.CANCELLED)
        self._emit("cancelled", task)
        return task

    def _prepare_runtimes(self, task: Task) -> dict[str, Any]:
        """根据任务模型列表载入运行时并准备推理会话。

        Args:
            task: 含模型标识和推理参数的待运行任务。

        Returns:
            按模型标识索引的已加载运行时字典。
        """

        runtimes: dict[str, Any] = {}
        for mid in task.model_ids:
            if mid not in self._model_manager._loaded:
                self._model_manager.load(mid)
            runtimes[mid] = self._model_manager._loaded[mid]
        return runtimes

    def run_image_task(self, task: Task) -> dict[str, Any]:
        """执行单图推理并保存帧结果和任务状态。

        Args:
            task: 要执行的单图推理任务。

        Returns:
            包含任务快照和单帧检测结果的字典。

        Raises:
            FileNotFoundError: 输入图片不存在或无法读取时抛出。
        """
        self._emit("created", task)
        task.transition(TaskStatus.RUNNING)
        self._emit("progress", task)
        try:
            runtimes = self._prepare_runtimes(task)
            session = InferenceSession.shared()
            task.session_id = session.session_id

            import cv2

            from app.utils.image_io import imread_unicode

            path = Path(task.params["media_path"])
            if not path.is_file():
                raise FileNotFoundError(f"not a valid image file: {path}")
            image = imread_unicode(path)
            if image is None:
                raise FileNotFoundError(f"cannot read image: {path}")

            frame = pipeline_engine.execute(
                session,
                image,
                task.model_ids,
                runtimes,
                media_ref=str(path),
                frame_id=0,
                class_filter=(task.params.get("overrides") or {}).get("class_filter"),
                max_side=(task.params.get("overrides") or {}).get("max_side"),
            )
            result_frame = {
                "frame_id": frame.frame_id,
                "media_path": str(path),
                "objects": [o.to_json() for o in frame.objects],
                "meta": frame.meta,
            }
            try:
                dao.save_frame_result(
                    task.task_id,
                    {"frame_id": frame.frame_id, "objects": result_frame["objects"], "meta": frame.meta},
                    media_path=str(path),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("save frame result failed: {}", exc)

            task.progress = 1.0
            task.progress_detail = {"done": 1, "total": 1}
            task.transition(TaskStatus.COMPLETED)
            self._emit("done", task)
            return {
                "task": task.to_dict(),
                "frame": result_frame,
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("image task failed {}", task.task_id)
            task.transition(TaskStatus.FAILED, error=str(exc))
            self._emit("done", task)
            raise

    def create_video_task(
        self,
        media_path: str,
        model_ids: list[str],
        *,
        skip_frame: int = 5,
        box_persistence: int = 5,
        overrides: dict[str, Any] | None = None,
    ) -> Task:
        """创建包含视频采样参数的推理任务。

        Args:
            media_path: 输入媒体文件路径。
            model_ids: 本次操作涉及的模型标识列表。
            skip_frame: 两次检测之间跳过的帧数。
            box_persistence: 检测框在后续帧中继续显示的帧数。
            overrides: 视频任务的采样或推理覆盖项。

        Returns:
            已登记的视频推理任务。
        """

        skip_frame = max(1, int(skip_frame))
        box_persistence = max(1, min(int(box_persistence), skip_frame))
        task = Task(
            type=TaskType.VIDEO,
            params={
                "media_path": media_path,
                "skip_frame": skip_frame,
                "box_persistence": box_persistence,
                "overrides": overrides or {},
            },
            model_ids=list(model_ids),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def run_video_task_async(self, task: Task) -> None:
        """在线程池中启动视频推理并转发进度。

        Args:
            task: 要在线程中执行的视频推理任务。
        """

        def worker() -> None:
            self._emit("created", task)
            try:
                task.transition(TaskStatus.RUNNING)
                runtimes = self._prepare_runtimes(task)
                session = InferenceSession.shared()
                task.session_id = session.session_id

                import cv2

                media_path = Path(task.params["media_path"])
                skip_frame = int(task.params.get("skip_frame") or 5)
                box_persistence = int(task.params.get("box_persistence") or 5)
                box_persistence = min(box_persistence, skip_frame)

                cap = open_video_capture(media_path)
                if not cap.isOpened():
                    cap.release()
                    raise FileNotFoundError(video_open_error_message(media_path))

                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0) or 25.0
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

                boxes_cache = []
                last_detect = -10**9
                detect_count = 0
                frame_id = 0
                saved_frames = 0

                while True:
                    if task.cancel_requested:
                        cap.release()
                        task.transition(TaskStatus.CANCELLED)
                        self._emit("done", task)
                        return

                    ok, image = cap.read()
                    if not ok:
                        break

                    is_detect = (frame_id - last_detect) >= skip_frame
                    meta = {
                        "fps": fps,
                        "width": width,
                        "height": height,
                        "skip_frame": skip_frame,
                        "box_persistence": box_persistence,
                        "is_detect_frame": is_detect,
                    }

                    if is_detect:
                        frame = pipeline_engine.execute(
                            session,
                            image,
                            task.model_ids,
                            runtimes,
                            media_ref=str(media_path),
                            frame_id=frame_id,
                            class_filter=(task.params.get("overrides") or {}).get("class_filter"),
                        )
                        boxes_cache = frame.objects
                        last_detect = frame_id
                        detect_count += 1
                        meta.update(frame.meta)
                        objects_now = frame.objects
                    else:
                        if (frame_id - last_detect) <= box_persistence:
                            objects_now = list(boxes_cache)
                        else:
                            objects_now = []

                    frame_payload = {
                        "frame_id": frame_id,
                        "media_path": str(media_path),
                        "objects": [o.to_json() for o in objects_now],
                        "meta": meta,
                    }

                    if is_detect or objects_now:
                        try:
                            dao.save_frame_result(
                                task.task_id,
                                {
                                    "frame_id": frame_id,
                                    "objects": frame_payload["objects"],
                                    "meta": meta,
                                },
                                media_path=str(media_path),
                            )
                            saved_frames += 1
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("save video frame failed: {}", exc)

                    if total > 0:
                        task.progress = min(1.0, (frame_id + 1) / total)
                    task.progress_detail = {
                        "done": frame_id + 1,
                        "total": total or (frame_id + 1),
                        "current_item": media_path.name,
                        "fps": fps,
                        "detect_count": detect_count,
                    }

                    push = is_detect or (frame_id % 15 == 0)
                    self._emit("progress", task, frame=frame_payload if push else None)

                    frame_id += 1

                if frame_id == 0:
                    cap.release()
                    raise RuntimeError(
                        f"无法从视频读取任何画面：{media_path}。文件可能损坏或编码不受支持。"
                    )

                cap.release()
                task.result_ref = f"video:{media_path}"
                task.progress = 1.0
                task.progress_detail = {
                    "done": frame_id,
                    "total": frame_id,
                    "detect_count": detect_count,
                    "saved_frames": saved_frames,
                }
                task.transition(TaskStatus.COMPLETED)
                self._emit(
                    "done",
                    task,
                    summary={
                        "frames": frame_id,
                        "detect_count": detect_count,
                        "saved_frames": saved_frames,
                        "fps": fps,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("video task failed {}", task.task_id)
                task.transition(TaskStatus.FAILED, error=str(exc))
                self._emit("done", task)

        th = threading.Thread(target=worker, name=f"task-{task.task_id}", daemon=True)
        self._threads[task.task_id] = th
        th.start()

    def create_export_task(
        self,
        *,
        source_task_id: str | None = None,
        source_video: str,
        output_path: str,
        label_template: str = "{id}:{class}",
        fps: float | None = None,
        hidden_classes: list[str] | None = None,
    ) -> Task:
        """创建基于已有任务结果的视频导出任务。

        Args:
            source_task_id: 提供帧结果的来源视频任务标识。
            source_video: 原始视频文件路径。
            output_path: 导出文件的目标路径。
            label_template: 用于拼接对象编号、类别和置信度的标签模板。
            fps: 输出视频的帧率。
            hidden_classes: 导出时需要隐藏的类别名称列表。

        Returns:
            已登记的视频导出任务。
        """

        task = Task(
            type=TaskType.EXPORT,
            params={
                "source_task_id": source_task_id,
                "source_video": source_video,
                "output_path": output_path,
                "label_template": label_template,
                "fps": fps,
                "hidden_classes": list(hidden_classes or []),
            },
            parent_task_id=source_task_id,
        )
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def run_export_task_async(self, task: Task) -> None:
        """在线程池中执行视频导出并报告完成或失败。

        Args:
            task: 要在线程中执行的视频导出任务。
        """

        def worker() -> None:
            self._emit("created", task)
            try:
                task.transition(TaskStatus.RUNNING)
                from app.export.video_exporter import export_video, load_frame_objects

                source_video = task.params["source_video"]
                output_path = task.params["output_path"]
                source_task_id = task.params.get("source_task_id")
                label_template = task.params.get("label_template") or "{id}:{class}"
                fps = task.params.get("fps")

                frame_objects = load_frame_objects(source_task_id) if source_task_id else {}

                def progress(p: float) -> None:
                    task.progress = p
                    task.progress_detail = {"done": int(p * 100), "total": 100, "current_item": output_path}
                    if int(p * 100) % 10 == 0:
                        self._emit("progress", task)

                def cancel() -> bool:
                    return task.cancel_requested

                summary = export_video(
                    source_video,
                    output_path,
                    frame_objects,
                    label_template=label_template,
                    fps=fps,
                    hidden_classes=task.params.get("hidden_classes") or [],
                    progress_cb=progress,
                    cancel_cb=cancel,
                )
                if task.cancel_requested:
                    task.transition(TaskStatus.CANCELLED)
                else:
                    task.progress = 1.0
                    task.result_ref = summary["output_path"]
                    task.transition(TaskStatus.COMPLETED)
                self._emit("done", task, summary=summary)
            except Exception as exc:  # noqa: BLE001
                logger.exception("export task failed {}", task.task_id)
                task.transition(TaskStatus.FAILED, error=str(exc))
                self._emit("done", task)

        th = threading.Thread(target=worker, name=f"task-{task.task_id}", daemon=True)
        self._threads[task.task_id] = th
        th.start()

    def run_folder_task_async(self, task: Task) -> None:
        """逐项执行文件夹图像检测并汇报每张图片的进度。

        Args:
            task: 要在线程中执行的目录推理任务。
        """

        def worker() -> None:
            self._emit("created", task)
            try:
                task.transition(TaskStatus.RUNNING)
                runtimes = self._prepare_runtimes(task)
                session = InferenceSession.shared()
                task.session_id = session.session_id

                folder = Path(task.params["folder_path"])
                from app.utils.image_io import imread_unicode
                from app.utils.media_list import IMAGE_EXTS, list_folder_images

                listed = list_folder_images(folder, recursive=bool((task.params.get("overrides") or {}).get("recursive")))
                file_paths = task.params.get("file_paths") or []
                if file_paths:
                    files = [Path(p) for p in file_paths if Path(p).is_file()]
                else:
                    files = [Path(x["path"]) for x in listed]
                total = len(files)
                if total == 0:
                    raise FileNotFoundError(f"no images in {folder} (supported: {sorted(IMAGE_EXTS)})")

                results: list[dict[str, Any]] = []
                for i, path in enumerate(files):
                    if task.cancel_requested:
                        task.transition(TaskStatus.CANCELLED)
                        self._emit("done", task)
                        return
            # 通知界面当前正在处理的帧和进度。
                    task.progress_detail = {
                        "done": i,
                        "total": total,
                        "current_item": path.name,
                        "processing_path": str(path),
                        "index": i,
                        "status": "processing",
                    }
                    self._emit(
                        "progress",
                        task,
                        frame={
                            "frame_id": i,
                            "media_path": str(path),
                            "objects": [],
                            "status": "processing",
                            "index": i,
                            "total": total,
                        },
                    )
                    image = imread_unicode(path)
                    if image is None:
                        continue
                    frame = pipeline_engine.execute(
                        session,
                        image,
                        task.model_ids,
                        runtimes,
                        media_ref=str(path),
                        frame_id=i,
                        class_filter=(task.params.get("overrides") or {}).get("class_filter"),
                    )
                    frame_payload = {
                        "frame_id": i,
                        "media_path": str(path),
                        "objects": [o.to_json() for o in frame.objects],
                        "meta": frame.meta,
                        "status": "done",
                        "index": i,
                        "total": total,
                    }
                    try:
                        dao.save_frame_result(
                            task.task_id,
                            {"frame_id": i, "objects": frame_payload["objects"], "meta": frame.meta},
                            media_path=str(path),
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("save frame result failed: {}", exc)
                    results.append(frame_payload)
                    task.progress = (i + 1) / total
                    task.progress_detail = {"done": i + 1, "total": total, "current_item": path.name}
                    self._emit("progress", task, frame=results[-1])

                task.result_ref = f"folder:{folder}"
                task.transition(TaskStatus.COMPLETED)
                self._emit("done", task, summary={"images": total, "results": len(results)})
            except Exception as exc:  # noqa: BLE001
                logger.exception("folder task failed {}", task.task_id)
                task.transition(TaskStatus.FAILED, error=str(exc))
                self._emit("done", task)

        th = threading.Thread(target=worker, name=f"task-{task.task_id}", daemon=True)
        self._threads[task.task_id] = th
        th.start()
