"""用于手工检查 model 相关流程的辅助脚本。"""

import asyncio
import json

import websockets


async def main() -> None:
    """运行 model 相关的烟雾检查流程。"""

    async with websockets.connect("ws://127.0.0.1:8765/ws") as ws:
        await ws.recv()  # 读取服务端首条握手消息。
        await ws.send(json.dumps({"type": "model.list", "id": "m1", "data": {}}))
        for _ in range(15):
            m = json.loads(await ws.recv())
            if m.get("type") == "model.list":
                models = m["data"].get("models", [])
                print("models:", [(x["model_id"], x["name"], x["loaded"]) for x in models])
                assert len(models) >= 1
                # 验证类别显示名映射接口。
                for c in models[0].get("class_list", []):
                    print(" class:", c)
                break
        print("MODEL_SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
