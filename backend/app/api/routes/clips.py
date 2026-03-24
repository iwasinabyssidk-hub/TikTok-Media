from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.job_manager import job_manager

router = APIRouter(prefix="/api/clips", tags=["clips"])


def _find_clip(clip_id: str) -> dict | None:
    for job in job_manager.all():
        for clip in job.clips:
            if clip["id"] == clip_id:
                return clip
    return None


@router.get("/{clip_id}/download")
async def download_clip(clip_id: str):
    clip = _find_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    path = Path(clip["video_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found on disk")
    return FileResponse(str(path), media_type="video/mp4", filename=path.name)


@router.get("/{clip_id}/thumbnail")
async def get_thumbnail(clip_id: str):
    clip = _find_clip(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    path = Path(clip["thumbnail_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk")
    return FileResponse(str(path), media_type="image/jpeg")
