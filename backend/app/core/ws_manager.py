from __future__ import annotations

import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, job_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[job_id].append(ws)

    def disconnect(self, job_id: str, ws: WebSocket) -> None:
        self._connections[job_id].discard(ws) if hasattr(self._connections[job_id], "discard") else None
        if ws in self._connections[job_id]:
            self._connections[job_id].remove(ws)

    async def broadcast(self, job_id: str, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(job_id, [])):
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(job_id, ws)

    def broadcast_sync(self, job_id: str, message: dict, loop: asyncio.AbstractEventLoop) -> None:
        """Thread-safe broadcast called from the job runner thread."""
        try:
            if not loop.is_closed():
                asyncio.run_coroutine_threadsafe(self.broadcast(job_id, message), loop)
        except RuntimeError:
            pass


ws_manager = WebSocketManager()
