"""Quick WS protocol smoke test for P1-M01."""

import asyncio
import json

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8765/ws"
    async with websockets.connect(uri) as ws:
        hello = json.loads(await ws.recv())
        assert hello["type"] == "system.hello", hello
        print("hello:", hello["type"], hello["data"].get("protocol_version"))

        await ws.send(json.dumps({"type": "ping", "id": "p2", "data": {}, "ts": 1234567890}))
        for _ in range(8):
            m = json.loads(await ws.recv())
            if m.get("type") == "pong":
                print("pong server_ts:", m["data"].get("server_ts"))
                assert m["data"].get("server_ts") == 1234567890
                break

        await ws.send(json.dumps({"type": "system.health", "id": "h2", "data": {}}))
        for _ in range(8):
            m = json.loads(await ws.recv())
            if m.get("type") == "system.health":
                print("health:", m["data"])
                break

        await ws.send(json.dumps({"type": "unknown.xyz", "id": "e1", "data": {}}))
        for _ in range(8):
            m = json.loads(await ws.recv())
            if m.get("error"):
                print("error:", m["error"]["code"], m["error"]["message"])
                assert m["error"]["code"] == "BAD_REQUEST"
                break

        await ws.send(json.dumps({"type": "system.hello_ack", "id": "a1", "data": {"client_version": "0.1.0"}}))
        await asyncio.sleep(0.2)
        print("SMOKE_OK")


if __name__ == "__main__":
    asyncio.run(main())
