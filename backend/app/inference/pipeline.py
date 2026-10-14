"""PipelineEngine: multi-model parallel inference + result merge."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from loguru import logger

from app.inference.base import FrameResult, ResultObject
from app.inference.session import InferenceSession


class PipelineEngine:
    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers

    def execute(
        self,
        session: InferenceSession,
        image: Any,
        model_ids: list[str],
        runtimes: dict[str, Any],
        *,
        media_ref: str = "",
        frame_id: int = 0,
        mode: str = "parallel",
        fail_fast: bool = False,
        class_filter: dict[str, list[str]] | None = None,
        max_side: int | None = None,
    ) -> FrameResult:
        t0 = time.perf_counter()
        collected: list[ResultObject] = []
        errors: dict[str, str] = {}

        infer_image = image
        sx = sy = 1.0
        if max_side and max_side > 0:
            try:
                h, w = image.shape[:2]
                longest = max(h, w)
                if longest > max_side:
                    scale = max_side / float(longest)
                    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                    import cv2

                    infer_image = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
                    sx, sy = w / nw, h / nh
            except Exception:  # noqa: BLE001
                infer_image = image

        def run_one(mid: str) -> tuple[str, list[ResultObject]]:
            rt = runtimes[mid]
            return mid, session.predict_objects(mid, rt, infer_image)

        def rescale(objs: list[ResultObject]) -> list[ResultObject]:
            if sx == 1.0 and sy == 1.0:
                return objs
            for o in objs:
                if o.geometry.bbox:
                    x1, y1, x2, y2 = o.geometry.bbox
                    o.geometry.bbox = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
            return objs

        targets = [m for m in model_ids if m in runtimes]
        missing = [m for m in model_ids if m not in runtimes]
        for m in missing:
            errors[m] = "runtime not loaded"

        if mode == "parallel" and len(targets) > 1:
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(targets))) as pool:
                futures = {pool.submit(run_one, mid): mid for mid in targets}
                for fut in as_completed(futures):
                    mid = futures[fut]
                    try:
                        _, objs = fut.result()
                        collected.extend(rescale(objs))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("pipeline node failed model={}: {}", mid, exc)
                        errors[mid] = str(exc)
                        if fail_fast:
                            raise
        else:
            for mid in targets:
                try:
                    _, objs = run_one(mid)
                    collected.extend(rescale(objs))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pipeline node failed model={}: {}", mid, exc)
                    errors[mid] = str(exc)
                    if fail_fast:
                        raise

        # merge: re-assign frame-local object id, keep model_id
        if class_filter:
            allowed_all = class_filter
            collected = [
                o
                for o in collected
                if (not allowed_all.get(o.model_id))
                or o.class_name in set(allowed_all.get(o.model_id) or [])
            ]
        collected.sort(key=lambda o: (-o.confidence, o.model_id, o.class_id))
        merged: list[ResultObject] = []
        for idx, obj in enumerate(collected, start=1):
            obj.id = idx
            merged.append(obj)

        elapsed = (time.perf_counter() - t0) * 1000
        return FrameResult(
            frame_id=frame_id,
            media_ref=media_ref,
            objects=merged,
            meta={
                "pipeline_ms": round(elapsed, 2),
                "models": targets,
                "errors": errors,
                "mode": mode,
            },
        )


pipeline_engine = PipelineEngine()
