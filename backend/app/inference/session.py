"""管理共享推理会话、逐帧检测缓存和运行统计。"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from loguru import logger

from app.inference.base import FrameResult, ResultObject


class FrameContext:
    """记录当前视频帧号以及各模型检测框的持续显示缓存。"""

    def __init__(self) -> None:
        """初始化FrameContext实例并准备运行所需状态。"""

        self.frame_id = 0
        self.skip_frame = 1
        self.box_persistence = 1
        self.boxes_cache: dict[str, list[ResultObject]] = {}
        self.last_detect_frame: dict[str, int] = {}

    def should_detect(self, model_id: str) -> bool:
        """根据最近推理帧和跳帧间隔判断是否执行本帧检测。

        Args:
            model_id: 目标模型的唯一标识。

        Returns:
            当前帧是否达到该模型的跳帧间隔。
        """

        last = self.last_detect_frame.get(model_id, -10**9)
        return (self.frame_id - last) >= self.skip_frame

    def put(self, model_id: str, objects: list[ResultObject]) -> None:
        """缓存当前模型的检测对象并记录执行帧号。

        Args:
            model_id: 目标模型的唯一标识。
            objects: 检测对象列表。
        """

        self.boxes_cache[model_id] = objects
        self.last_detect_frame[model_id] = self.frame_id

    def get(self, model_id: str) -> list[ResultObject]:
        """返回仍在持续显示期限内的缓存检测对象。

        Args:
            model_id: 目标模型的唯一标识。

        Returns:
            缓存尚未过期的检测对象列表；没有可用缓存时返回空列表。
        """

        last = self.last_detect_frame.get(model_id)
        if last is None:
            return []
        if (self.frame_id - last) > self.box_persistence:
            return []
        return self.boxes_cache.get(model_id, [])

    def reset(self) -> None:
        """清空当前视频会话的检测对象缓存和帧号记录。"""

        self.boxes_cache.clear()
        self.last_detect_frame.clear()


class InferenceSession:
    """为任务共享已加载运行时并串行化单个模型的预测调用。"""

    _instance: "InferenceSession | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """初始化会话标识、帧缓存和模型调用锁。"""

        self.session_id = f"s_{uuid.uuid4().hex[:12]}"
        self.frame_ctx = FrameContext()
        self._locks: dict[str, threading.Lock] = {}
        self._predict_count = 0

    @classmethod
    def shared(cls) -> "InferenceSession":
        """获取进程内唯一的共享推理会话。

        Returns:
            进程内唯一的推理会话实例。
        """

        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def predict_objects(self, model_id: str, runtime: Any, image: Any) -> list[ResultObject]:
        """串行调用指定模型的预测接口并记录推理耗时。

        Args:
            model_id: 目标模型的唯一标识。
            runtime: 负责执行模型推理的运行时实例。
            image: 待处理的图像数据。

        Returns:
            指定模型的检测对象列表。
        """

        lock = self._locks.setdefault(model_id, threading.Lock())
        with lock:
            t0 = time.perf_counter()
            objects = runtime.predict(image)
            self._predict_count += 1
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("predict model={} n={} {:.1f}ms", model_id, len(objects), elapsed)
            return objects

    def stats(self) -> dict[str, Any]:
        """汇总推理会话标识、预测次数和当前帧号。

        Returns:
            包含会话标识、预测次数和当前帧号的统计字典。
        """

        return {
            "session_id": self.session_id,
            "predict_count": self._predict_count,
            "frame_id": self.frame_ctx.frame_id,
        }
