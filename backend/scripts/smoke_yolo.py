"""Smoke real YOLO (ultralytics) via model.load + detect.image."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import websockets

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "logs" / "smoke_sample.jpg"


def ensure_sample() -> None:
    SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    if SAMPLE.exists():
        return
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (210, 220, 230)
    cv2.rectangle(img, (80, 120), (220, 400), (60, 80, 160), -1)
    cv2.imwrite(str(SAMPLE), img)


async def main() -> None:
    ensure_sample()
    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(json.dumps({"type": "model.list", "id": "m0", "data": {}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "model.list":
                ids = [x["model_id"] for x in m["data"]["models"]]
                print("models", ids)
                break

        await ws.send(
            json.dumps({"type": "model.load", "id": "l1", "data": {"model_ids": ["coco_yolov8n"]}})
        )
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "model.load":
                print("load ok", m["data"]["models"][0]["model_id"], "loaded", m["data"]["models"][0]["loaded"])
                break
            if m.get("error"):
                print(m)
                raise SystemExit(1)

        await ws.send(
            json.dumps(
                {
                    "type": "detect.image",
                    "id": "d1",
                    "data": {
                        "media_path": str(SAMPLE),
                        "model_ids": ["coco_yolov8n"],
                        "overrides": {"conf": 0.1},
                    },
                }
            )
        )
        for _ in range(30):
            m = json.loads(await ws.recv())
            if m.get("type") == "detect.result":
                objs = m["data"]["frame"]["objects"]
                print("objects", [(o["display_name"], round(o["confidence"], 3)) for o in objs[:5]])
                print("YOLO_SMOKE_OK")
                return
            if m.get("error"):
                print("err", m)
                raise SystemExit(1)
        raise SystemExit("timeout")


if __name__ == "__main__":
    asyncio.run(main())
