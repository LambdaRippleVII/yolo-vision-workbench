"""协调多模型推理、类别筛选、坐标还原和结果合并。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from loguru import logger

from app.inference.base import FrameResult, ResultObject
from app.inference.session import InferenceSession


class PipelineEngine:
    """执行多个模型的推理并整合为统一帧结果。"""

    def __init__(self, max_workers: int = 4) -> None:
        """初始化PipelineEngine实例并准备运行所需状态。

        Args:
            max_workers: 线程池允许同时执行的最大工作线程数。
        """

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
        """按执行策略运行多个模型，筛选结果并合并为一帧输出。

        Args:
            session: 负责协调模型调用和帧状态的推理会话。
            image: 待处理的图像数据。
            model_ids: 本次操作涉及的模型标识列表。
            runtimes: 按模型标识索引的推理运行时集合。
            media_ref: 当前帧对应的媒体引用或文件路径。
            frame_id: 视频帧的零基索引。
            mode: 选择运行或显示行为的模式。
            fail_fast: 出现首个模型错误时是否立即终止流水线。
            class_filter: 按模型标识设置的允许类别清单。
            max_side: 推理图像最长边允许使用的像素上限。

        Returns:
            合并多模型检测对象、耗时和错误信息的帧结果。
        """

        t0 = time.perf_counter()
        collected: list[ResultObject] = []
        errors: dict[str, str] = {}

        infer_image = image
        sx = sy = 1.0
        if max_side and max_side > 0:
            # 仅在最长边超过限制时缩小输入，并记录比例以便稍后还原检测框。
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
                # 预处理失败时保留原图，避免缩放错误阻断整帧推理。
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
        # 缺少运行时的模型单独记录错误，已加载的模型仍可继续推理。
        for m in missing:
            errors[m] = "runtime not loaded"

        if mode == "parallel" and len(targets) > 1:
            # 多模型互相独立时并行执行；失败是否中断由 fail_fast 决定。
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

        # 按类别筛选并排序后，重新分配当前帧内连续的对象编号。
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


# 供任务管理器共享使用的多模型推理流水线实例。
pipeline_engine = PipelineEngine()
