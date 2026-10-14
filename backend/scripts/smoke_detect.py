"""End-to-end detect.image smoke via WebSocket + mock model."""

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
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (220, 230, 240)
    cv2.rectangle(img, (100, 100), (280, 360), (80, 120, 200), -1)
    cv2.imwrite(str(SAMPLE), img)


async def main() -> None:
    ensure_sample()
    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=10_000_000) as ws:
        await ws.recv()

        await ws.send(json.dumps({"type": "model.load", "id": "l1", "data": {"model_ids": ["demo"]}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "model.load":
                print("load:", m.get("data"))
                break

        await ws.send(
            json.dumps(
                {
                    "type": "detect.image",
                    "id": "d1",
                    "data": {"media_path": str(SAMPLE), "model_ids": ["demo"], "overrides": {"conf": 0.4}},
                }
            )
        )
        for _ in range(15):
            m = json.loads(await ws.recv())
            if m.get("type") == "detect.result":
                objs = m["data"]["frame"]["objects"]
                print("objects:", [(o["id"], o["display_name"], o["geom"]["bbox"]) for o in objs])
                assert len(objs) >= 1
                assert objs[0]["display_name"] == "人员"
                print("DETECT_SMOKE_OK")
                return
            if m.get("error"):
                print("error", m)
                raise SystemExit(1)
        raise SystemExit("no detect.result")


if __name__ == "__main__":
    asyncio.run(main())
