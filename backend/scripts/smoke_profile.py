"""用于手工检查 profile 相关流程的辅助脚本。"""

from __future__ import annotations

import asyncio
import json

import websockets


async def main() -> None:
    """运行 profile 相关的烟雾检查流程。

    Raises:
        SystemExit: 将配置方案烟雾检查失败状态传递给命令行。
    """

    async with websockets.connect("ws://127.0.0.1:8765/ws") as ws:
        await ws.recv()

        await ws.send(
            json.dumps(
                {
                    "type": "profile.save",
                    "id": "p1",
                    "data": {
                        "name": "工地检测",
                        "payload": {
                            "models": [{"model_id": "demo", "enabled": True, "conf": 0.5}],
                            "render": {"label_template": "{id}:{class}"},
                            "runtime": {"skip_frame": 3, "box_persistence": 3},
                        },
                    },
                }
            )
        )
        profile_id = None
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "profile.save":
                profile_id = m["data"]["profile"]["profile_id"]
                print("saved", profile_id, m["data"]["profile"]["name"])
                break

        await ws.send(json.dumps({"type": "profile.list", "id": "p2", "data": {}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "profile.list":
                names = [p["name"] for p in m["data"]["profiles"]]
                print("profiles", names)
                assert "工地检测" in names or profile_id in [p["profile_id"] for p in m["data"]["profiles"]]
                break

        await ws.send(json.dumps({"type": "profile.apply", "id": "p3", "data": {"profile_id": profile_id}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "profile.apply":
                payload = m["data"]["profile"]["payload"]
                print("applied conf", payload["models"][0]["conf"], "skip", payload["runtime"]["skip_frame"])
                assert payload["models"][0]["conf"] == 0.5
                print("PROFILE_SMOKE_OK")
                return
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
