"""Smoke: class_filter + export.frames + camera.record."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "logs" / "smoke_video.mp4"
OUTDIR = ROOT / "logs" / "frame_export"


async def main() -> None:
    assert SAMPLE.exists()
    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=20_000_000) as ws:
        await ws.recv()
        # class filter: only person
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
                        "overrides": {"class_filter": {"demo": ["person"]}},
                    },
                }
            )
        )
        task_id = None
        for _ in range(200):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if m.get("type") == "task.created":
                task_id = m["data"]["task"]["task_id"]
            if m.get("type") == "task.done":
                assert m["data"]["status"] == "completed"
                break

        await ws.send(
            json.dumps({"type": "result.frame", "id": "r1", "data": {"task_id": task_id, "frame_id": 0}})
        )
        names = []
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "result.frame":
                names = [o["class_name"] for o in m["data"]["objects"]]
                break
        print("filtered names", names)
        assert all(n == "person" for n in names), names

        OUTDIR.mkdir(exist_ok=True)
        await ws.send(
            json.dumps(
                {
                    "type": "export.frames",
                    "id": "e1",
                    "data": {
                        "task_id": task_id,
                        "video_path": str(SAMPLE),
                        "output_dir": str(OUTDIR),
                        "frame_ids": [0, 5, 10],
                    },
                }
            )
        )
        for _ in range(30):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if m.get("type") == "export.frames":
                print("frames saved", m["data"])
                assert m["data"]["count"] >= 1
                break

        # camera record
        await ws.send(
            json.dumps(
                {
                    "type": "camera.open",
                    "id": "c1",
                    "data": {
                        "source_type": "rtsp",
                        "source": str(SAMPLE),
                        "model_ids": ["demo"],
                        "skip_frame": 5,
                        "box_persistence": 5,
                    },
                }
            )
        )
        stream_id = None
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "camera.open":
                stream_id = m["data"]["stream_id"]
                break

        rec = ROOT / "logs" / "record_test.mp4"
        await ws.send(
            json.dumps(
                {
                    "type": "camera.record",
                    "id": "r1",
                    "data": {"stream_id": stream_id, "action": "start", "output_path": str(rec)},
                }
            )
        )
        for _ in range(50):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "stream.frame":
                break

        await ws.send(
            json.dumps({"type": "camera.record", "id": "r2", "data": {"stream_id": stream_id, "action": "stop"}})
        )
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "camera.record" and m["data"].get("action") == "stop":
                print("record", m["data"])
                assert Path(m["data"]["output_path"]).exists()
                break

        await ws.send(json.dumps({"type": "camera.close", "id": "c2", "data": {"stream_id": stream_id}}))
        print("PRODUCT_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
