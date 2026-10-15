"""Live camera / RTSP stream task (preview + optional detect)."""

from __future__ import annotations

import base64
import threading
import time
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from app.inference.pipeline import pipeline_engine
from app.inference.session import InferenceSession
from app.utils.image_io import open_video_capture, video_open_error_message


class StreamSession:
    def __init__(
        self,
        *,
        stream_id: str,
        source: str | int,
        model_ids: list[str],
        skip_frame: int = 5,
        box_persistence: int = 5,
        emit: Callable[[dict[str, Any]], None],
        model_manager: Any,
        record_path: str | None = None,
        record_fps: float | None = None,
    ) -> None:
        self.stream_id = stream_id
        self.source = source
        self.model_ids = model_ids
        self.skip_frame = max(1, int(skip_frame))
        self.box_persistence = max(1, min(int(box_persistence), self.skip_frame))
        self._emit = emit
        self._model_manager = model_manager
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._cap = None
        self.frame_count = 0
        self.detect_count = 0
        self.last_error: str | None = None
        self.record_path = record_path
        self.record_fps = float(record_fps) if record_fps else None
        self._writer = None
        self._recording = False
        self.record_frames = 0
        self.record_task_id: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name=f"stream-{self.stream_id}", daemon=True)
        self._thread.start()

    def start_recording(self, path: str, *, fps: float | None = None, task_id: str | None = None) -> None:
        self.record_path = path
        self.record_fps = fps if fps and fps > 0 else self.record_fps
        self.record_task_id = task_id
        self._recording = True
        self.record_frames = 0

    def stop_recording(self) -> dict[str, Any]:
        self._recording = False
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception:  # noqa: BLE001
                pass
            self._writer = None
        return {
            "output_path": self.record_path,
            "record_frames": self.record_frames,
            "task_id": self.record_task_id,
            "fps": self.record_fps or 20.0,
        }

    def set_model_ids(self, model_ids: list[str]) -> list[str]:
        """Hot-swap detection models while stream is running (empty = preview only)."""
        self.model_ids = list(model_ids or [])
        return list(self.model_ids)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # noqa: BLE001
                pass
            self._cap = None

    def _run(self) -> None:
        import cv2


        try:
            local_video_path: Path | None = None
            if isinstance(self.source, str):
                candidate = Path(self.source).expanduser()
                if candidate.is_file():
                    local_video_path = candidate
                    self._cap = open_video_capture(candidate)
                else:
                    self._cap = cv2.VideoCapture(self.source)
            else:
                self._cap = cv2.VideoCapture(self.source)
            if not self._cap.isOpened():
                if local_video_path is not None:
                    raise RuntimeError(video_open_error_message(local_video_path))
                raise RuntimeError(f"cannot open stream: {self.source}")

            runtimes = {}
            for mid in self.model_ids:
                if mid not in self._model_manager._loaded:
                    self._model_manager.load(mid)
                runtimes[mid] = self._model_manager._loaded[mid]

            session = InferenceSession.shared()
            boxes_cache = []
            last_detect = -10**9

            while not self._stop.is_set():
                ok, frame = self._cap.read()
                if not ok:
                    # RTSP may drop; brief wait and continue
                    time.sleep(0.05)
                    continue

                self.frame_count += 1
                frame_id = self.frame_count
                is_detect = (frame_id - last_detect) >= self.skip_frame
                objects_json: list[dict[str, Any]] = []

                if is_detect and self.model_ids:
                    try:
                        runtimes = {}
                        for mid in self.model_ids:
                            if mid not in self._model_manager._loaded:
                                self._model_manager.load(mid)
                            runtimes[mid] = self._model_manager._loaded[mid]
                        result = pipeline_engine.execute(
                            session,
                            frame,
                            self.model_ids,
                            runtimes,
                            media_ref=str(self.source),
                            frame_id=frame_id,
                        )
                        boxes_cache = result.objects
                        last_detect = frame_id
                        self.detect_count += 1
                    except Exception as exc:  # noqa: BLE001
                        self.last_error = str(exc)
                        logger.warning("stream detect failed: {}", exc)

                if (frame_id - last_detect) <= self.box_persistence:
                    objects_now = list(boxes_cache)
                else:
                    objects_now = []

                objects_json = [o.to_json() for o in objects_now]

                ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue
                jpeg_b64 = base64.b64encode(buf.tobytes()).decode("ascii")

                if self._recording and self.record_path:
                    if self._writer is None:
                        h, w = frame.shape[:2]
                        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                        fps = float(self.record_fps or 20.0)
                        self._writer = cv2.VideoWriter(self.record_path, fourcc, fps, (w, h))
                    if self._writer is not None:
                        self._writer.write(frame)
                        self.record_frames += 1
                        # persist results so editor can open without re-detect
                        if self.record_task_id:
                            try:
                                from app.database import dao as db_dao

                                db_dao.save_frame_result(
                                    self.record_task_id,
                                    {
                                        "frame_id": self.record_frames - 1,
                                        "objects": objects_json,
                                        "meta": {
                                            "is_detect_frame": is_detect,
                                            "stream_id": self.stream_id,
                                        },
                                    },
                                    media_path=str(self.record_path),
                                )
                            except Exception as exc:  # noqa: BLE001
                                logger.warning("save record frame failed: {}", exc)

                self._emit(
                    {
                        "type": "stream.frame",
                        "data": {
                            "stream_id": self.stream_id,
                            "frame_id": frame_id,
                            "detect_count": self.detect_count,
                            "objects": objects_json,
                            "jpeg_b64": jpeg_b64,
                            "data_url": f"data:image/jpeg;base64,{jpeg_b64}",
                            "is_detect": is_detect,
                            "recording": self._recording,
                            "record_frames": self.record_frames,
                        },
                    }
                )

                # light throttle ~15 fps emit
                time.sleep(0.066)

        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            logger.exception("stream failed {}", self.stream_id)
            self._emit(
                {
                    "type": "stream.error",
                    "data": {"stream_id": self.stream_id, "message": str(exc)},
                }
            )
        finally:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:  # noqa: BLE001
                    pass
                self._cap = None
            self._emit(
                {
                    "type": "stream.stopped",
                    "data": {
                        "stream_id": self.stream_id,
                        "frames": self.frame_count,
                        "detect_count": self.detect_count,
                    },
                }
            )
