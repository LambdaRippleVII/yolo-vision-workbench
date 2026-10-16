"""用于手工检查 task persist 相关流程的辅助脚本。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import cv2
import numpy as np
import websockets

# 后端仓库目录的绝对路径。
ROOT = Path(__file__).resolve().parents[2]
# 烟雾检查使用的媒体样例文件路径。
SAMPLE = ROOT / "logs" / "smoke_sample.jpg"


async def main() -> None:
    """运行 task persist 相关的烟雾检查流程。

    Raises:
        SystemExit: 将任务持久化烟雾检查失败状态传递给命令行。
    """

    if not SAMPLE.exists():
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        img[:] = (200, 210, 220)
        cv2.imwrite(str(SAMPLE), img)

    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "detect.image",
                    "id": "d1",
                    "data": {"media_path": str(SAMPLE), "model_ids": ["demo"]},
                }
            )
        )
        task_id = None
        for _ in range(15):
            m = json.loads(await ws.recv())
            if m.get("type") == "detect.result":
                task_id = m["data"]["task"]["task_id"]
                print("detect task", task_id)
                break

        await ws.send(json.dumps({"type": "task.list", "id": "t1", "data": {}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "task.list":
                tasks = m["data"]["tasks"]
                print("task.count", len(tasks))
                assert any(x["task_id"] == task_id for x in tasks)
                print("TASK_PERSIST_OK")
                return
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
