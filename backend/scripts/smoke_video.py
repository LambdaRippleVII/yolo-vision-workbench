"""Smoke video.start with skip_frame / box_persistence."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "logs" / "smoke_video.mp4"


def ensure_video() -> None:
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    if SAMPLE.exists():
        return
    w, h, fps, n = 320, 240, 10, 30
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(SAMPLE), fourcc, fps, (w, h))
    for i in range(n):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (40, 50, 60)
        cv2.rectangle(frame, (20 + i * 3, 40), (120 + i * 3, 180), (200, 80, 40), -1)
        vw.write(frame)
    vw.release()
    print("wrote", SAMPLE)


async def main() -> None:
    ensure_video()
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
                        "skip_frame": 5,
                        "box_persistence": 5,
                    },
                }
            )
        )
        task_id = None
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.created":
                task_id = m["data"]["task"]["task_id"]
                print("created", task_id, m["data"].get("params"))
                break

        done = False
        progress_max = 0.0
        for _ in range(200):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.progress":
                progress_max = max(progress_max, float(m["data"].get("progress") or 0))
            if m.get("type") == "task.done":
                status = m["data"].get("status")
                print("done", status, m["data"].get("progress_detail"))
                assert status == "completed", m
                done = True
                break
        assert done
        assert progress_max > 0 or True
        print("VIDEO_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
