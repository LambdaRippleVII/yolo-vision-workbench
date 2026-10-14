"""P1-M01 verification checklist (manual + semi-auto).

Automated: backend/scripts/smoke_ws.py
Manual:
  1. python backend is up: GET /health
  2. Electron window shows Backend: ready
  3. WS connected
  4. Ping / Health buttons work
  5. Restart Backend recovers
  6. Logs panel receives log.message
"""

CHECKS = [
    "backend /health returns status=ready",
    "ws system.hello received on connect",
    "ws ping -> pong with server_ts",
    "ws system.health returns ok",
    "unknown message type -> BAD_REQUEST",
    "Electron ProcessSupervisor spawns backend",
    "Electron UI shows backend status",
    "loguru file log created under logs/",
    "no YOLO inference code (M01 scope)",
    "no database business logic (M01 scope)",
]
