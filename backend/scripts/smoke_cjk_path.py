"""用于手工检查 cjk path 相关流程的辅助脚本。"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import websockets

# 后端仓库目录的绝对路径。
ROOT = Path(__file__).resolve().parents[2]
# 中文路径兼容检查使用的源图像路径。
SRC = ROOT / "logs" / "smoke_sample.jpg"
# 中文路径兼容检查的目标图像路径。
CJK = ROOT / "logs" / "中文路径测试" / "测试图片.jpg"


async def main() -> None:
    """运行 cjk path 相关的烟雾检查流程。

    Raises:
        SystemExit: 将中文路径烟雾检查失败状态传递给命令行。
    """

    CJK.parent.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        img[:] = (180, 190, 200)
        cv2.imwrite(str(SRC), img)
    shutil.copy(SRC, CJK)
    print("cjk path", CJK, CJK.exists())

    async with websockets.connect("ws://127.0.0.1:8765/ws", max_size=10_000_000) as ws:
        await ws.recv()
        await ws.send(
            json.dumps(
                {
                    "type": "detect.image",
                    "id": "d1",
                    "data": {
                        "media_path": str(CJK),
                        "model_ids": ["demo"],
                        "overrides": {"conf": 0.4, "max_side": 640},
                    },
                }
            )
        )
        for _ in range(20):
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if m.get("type") == "detect.result":
                print("objects", len(m["data"]["frame"]["objects"]))
                print("CJK_PATH_OK")
                return
            if m.get("error"):
                print("err", m)
                raise SystemExit(1)
        raise SystemExit("timeout")


if __name__ == "__main__":
    asyncio.run(main())
