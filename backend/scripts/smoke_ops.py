"""用于手工检查 ops 相关流程的辅助脚本。"""

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
    """运行 ops 相关的烟雾检查流程。"""

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
                break

        await ws.send(
            json.dumps(
                {
                    "type": "result.frame",
                    "id": "r1",
                    "data": {"task_id": task_id, "frame_id": 0},
                }
            )
        )
        objs = []
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "result.frame":
                objs = m["data"]["objects"]
                break
        assert objs
        target = objs[0]
        await ws.send(
            json.dumps(
                {
                    "type": "ops.setVisible",
                    "id": "o1",
                    "data": {
                        "task_id": task_id,
                        "frame_id": 0,
                        "object_id": target["id"],
                        "model_id": target["model_id"],
                        "visible": False,
                    },
                }
            )
        )
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "ops.setVisible":
                print("setVisible", m["data"])
                assert m["data"]["ok"]
                break

        await ws.send(
            json.dumps(
                {
                    "type": "result.frame",
                    "id": "r2",
                    "data": {"task_id": task_id, "frame_id": 0},
                }
            )
        )
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "result.frame":
                vis = {o["id"]: o["visible"] for o in m["data"]["objects"]}
                print("visibility", vis)
                assert vis[target["id"]] is False
                break

        await ws.send(json.dumps({"type": "ops.list", "id": "ol", "data": {"task_id": task_id}}))
        for _ in range(20):
            m = json.loads(await ws.recv())
            if m.get("type") == "ops.list":
                actions = [x["action"] for x in m["data"]["ops"]]
                print("ops", actions)
                assert "hide_object" in actions
                break

        print("OPS_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
