"""Smoke export.video after video detection."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "logs" / "smoke_video.mp4"
OUT = ROOT / "logs" / "smoke_video_export.mp4"


def ensure_video() -> None:
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    if SAMPLE.exists():
        return
    w, h, fps, n = 320, 240, 10, 20
    vw = cv2.VideoWriter(str(SAMPLE), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(n):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (30, 40, 50)
        cv2.rectangle(frame, (30, 30), (150, 200), (200, 100, 50), -1)
        vw.write(frame)
    vw.release()


async def main() -> None:
    ensure_video()
    if OUT.exists():
        OUT.unlink()
    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=20_000_000) as ws:
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "video.start",
                    "id": "v1",
                    "data": {
                        "media_path": str(SAMPLE),
                        "model_ids": ["demo"],
                        "skip_frame": 4,
                        "box_persistence": 4,
                    },
                }
            )
        )
        source_task = None
        for _ in range(200):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.created":
                source_task = m["data"]["task"]["task_id"]
            if m.get("type") == "task.done":
                assert m["data"]["status"] == "completed"
                print("video done", m["data"].get("summary"))
                break

        await ws.send(
            json.dumps(
                {
                    "type": "export.video",
                    "id": "e1",
                    "data": {
                        "source_video": str(SAMPLE),
                        "output_path": str(OUT),
                        "source_task_id": source_task,
                        "label_template": "{id}:{class}",
                    },
                }
            )
        )
        for _ in range(200):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.done" and m["data"].get("type") == "export":
                print("export", m["data"]["status"], m["data"].get("summary"))
                assert m["data"]["status"] == "completed"
                break
        assert OUT.exists() and OUT.stat().st_size > 1000
        cap = cv2.VideoCapture(str(OUT))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        print("export frames", frames, "size", OUT.stat().st_size)
        print("EXPORT_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
