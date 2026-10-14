"""Smoke camera/stream using a local video file as source (cv2 can open path)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "logs" / "smoke_video.mp4"


async def main() -> None:
    assert SAMPLE.exists()
    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=20_000_000) as ws:
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "camera.open",
                    "id": "c1",
                    "data": {
                        "source_type": "rtsp",
                        "source": str(SAMPLE),
                        "model_ids": ["demo"],
                        "skip_frame": 3,
                        "box_persistence": 3,
                    },
                }
            )
        )
        stream_id = None
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "camera.open":
                stream_id = m["data"]["stream_id"]
                print("open", stream_id)
                break
            if m.get("error"):
                print(m)
                raise SystemExit(1)

        frames = 0
        for _ in range(80):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "stream.frame":
                frames += 1
                if frames <= 2:
                    print("frame", m["data"]["frame_id"], "objs", len(m["data"]["objects"]), "detect", m["data"]["is_detect"])
                if frames >= 5:
                    break
            if m.get("type") == "stream.error":
                print("err", m)
                raise SystemExit(1)

        await ws.send(json.dumps({"type": "camera.close", "id": "c2", "data": {"stream_id": stream_id}}))
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if m.get("type") == "camera.close":
                print("closed", m["data"])
                break
        assert frames >= 1
        print("CAMERA_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
