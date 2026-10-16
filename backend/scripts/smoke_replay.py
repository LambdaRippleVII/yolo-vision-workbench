"""用于手工检查 replay 相关流程的辅助脚本。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import websockets

# 后端仓库目录的绝对路径。
ROOT = Path(__file__).resolve().parents[2]
# 烟雾检查使用的媒体样例文件路径。
SAMPLE = ROOT / "logs" / "smoke_video.mp4"


async def main() -> None:
    """运行 replay 相关的烟雾检查流程。"""

    assert SAMPLE.exists(), SAMPLE
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
        for _ in range(200):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.created":
                task_id = m["data"]["task"]["task_id"]
            if m.get("type") == "task.done":
                assert m["data"]["status"] == "completed"
                break

        await ws.send(json.dumps({"type": "result.frames", "id": "f1", "data": {"task_id": task_id}}))
        frames = []
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "result.frames":
                frames = m["data"]["frames"]
                print("frames", len(frames), frames[:3])
                assert len(frames) > 0
                break

        fid = frames[0]["frame_id"]
        await ws.send(
            json.dumps({"type": "result.frame", "id": "f2", "data": {"task_id": task_id, "frame_id": fid}})
        )
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "result.frame":
                objs = m["data"]["objects"]
                print("objects", len(objs), [o["display_name"] for o in objs])
                break

        await ws.send(
            json.dumps(
                {
                    "type": "result.preview",
                    "id": "f3",
                    "data": {"video_path": str(SAMPLE), "frame_id": fid},
                }
            )
        )
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "result.preview":
                assert m["data"]["data_url"].startswith("data:image/jpeg")
                print("preview_bytes", len(m["data"]["jpeg_b64"]))
                break

        print("REPLAY_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
