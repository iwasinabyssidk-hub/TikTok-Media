from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path so TTM modules are importable
_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.clips import router as clips_router
from app.api.routes.config_route import router as config_router
from app.api.routes.jobs import router as jobs_router
from app.api.websocket import router as ws_router

app = FastAPI(title="TTM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(clips_router)
app.include_router(config_router)
app.include_router(ws_router)

# Serve output files statically
_output_dir = _PROJECT_ROOT / "output"
_output_dir.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=str(_output_dir)), name="output")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
