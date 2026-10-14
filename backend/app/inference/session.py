"""InferenceSession: per-work context binding models and frame cache."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from loguru import logger

from app.inference.base import FrameResult, ResultObject


class FrameContext:
    def __init__(self) -> None:
        self.frame_id = 0
        self.skip_frame = 1
        self.box_persistence = 1
        self.boxes_cache: dict[str, list[ResultObject]] = {}
        self.last_detect_frame: dict[str, int] = {}

    def should_detect(self, model_id: str) -> bool:
        last = self.last_detect_frame.get(model_id, -10**9)
        return (self.frame_id - last) >= self.skip_frame

    def put(self, model_id: str, objects: list[ResultObject]) -> None:
        self.boxes_cache[model_id] = objects
        self.last_detect_frame[model_id] = self.frame_id

    def get(self, model_id: str) -> list[ResultObject]:
        last = self.last_detect_frame.get(model_id)
        if last is None:
            return []
        if (self.frame_id - last) > self.box_persistence:
            return []
        return self.boxes_cache.get(model_id, [])

    def reset(self) -> None:
        self.boxes_cache.clear()
        self.last_detect_frame.clear()


class InferenceSession:
    """Binds model_id -> loaded runtime. Shared by tasks and interactive detect."""

    _instance: "InferenceSession | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.session_id = f"s_{uuid.uuid4().hex[:12]}"
        self.frame_ctx = FrameContext()
        self._locks: dict[str, threading.Lock] = {}
        self._predict_count = 0

    @classmethod
    def shared(cls) -> "InferenceSession":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def predict_objects(self, model_id: str, runtime: Any, image: Any) -> list[ResultObject]:
        lock = self._locks.setdefault(model_id, threading.Lock())
        with lock:
            t0 = time.perf_counter()
            objects = runtime.predict(image)
            self._predict_count += 1
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("predict model={} n={} {:.1f}ms", model_id, len(objects), elapsed)
            return objects

    def stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "predict_count": self._predict_count,
            "frame_id": self.frame_ctx.frame_id,
        }
