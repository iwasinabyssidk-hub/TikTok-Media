from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.job_manager import job_manager
from app.core.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/jobs/{job_id}")
async def job_websocket(job_id: str, websocket: WebSocket):
    job = job_manager.get(job_id)
    if not job:
        await websocket.close(code=4004)
        return

    await ws_manager.connect(job_id, websocket)

    # Send buffered logs immediately on connect
    for line in job.logs[-100:]:
        await websocket.send_text(json.dumps({"type": "log", "level": "INFO", "message": line}))
    await websocket.send_text(json.dumps({"type": "progress", "value": job.progress}))
    await websocket.send_text(json.dumps({"type": "status", "status": job.status}))

    try:
        while True:
            # Keep connection alive; actual messages come from broadcast_sync
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, asyncio.CancelledError, Exception):
        pass
    finally:
        ws_manager.disconnect(job_id, websocket)
