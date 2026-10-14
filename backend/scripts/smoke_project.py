"""Smoke: project create / list / open."""

from __future__ import annotations

import asyncio
import json

import websockets


async def main() -> None:
    async with websockets.connect("ws://127.0.0.1:8765/ws") as ws:
        await ws.recv()

        await ws.send(json.dumps({"type": "project.create", "id": "c1", "data": {"name": "工地一期"}}))
        project_id = None
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "project.create":
                project_id = m["data"]["project"]["project_id"]
                print("created", project_id)
                break

        await ws.send(json.dumps({"type": "project.open", "id": "o1", "data": {"project_id": project_id}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "project.open":
                print("opened", m["data"]["project"]["name"], m["data"]["current_project_id"])
                assert m["data"]["current_project_id"] == project_id
                break

        await ws.send(json.dumps({"type": "project.list", "id": "l1", "data": {}}))
        for _ in range(10):
            m = json.loads(await ws.recv())
            if m.get("type") == "project.list":
                names = [p["name"] for p in m["data"]["projects"]]
                print("projects", names)
                assert "工地一期" in names
                print("PROJECT_SMOKE_OK")
                return
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
