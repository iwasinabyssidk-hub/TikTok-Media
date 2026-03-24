from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.core.job_manager import job_manager
from app.core.job_runner import run_job
from app.models.clip import ClipResponse
from app.models.job import JobCreate, JobResponse

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        progress=job.progress,
        channels=job.channels,
        num_clips=job.num_clips,
        videos_per_channel=job.videos_per_channel,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        total_clips=len(job.clips),
        error=job.error,
        run_subdir=job.run_subdir,
        logs=job.logs[-200:],  # last 200 lines to avoid huge payloads
        report=job.report,
    )


@router.post("", status_code=201, response_model=JobResponse)
async def create_job(body: JobCreate):
    job = job_manager.create(
        channels=body.channels,
        num_clips=body.num_clips,
        videos_per_channel=body.videos_per_channel,
        min_clip_duration=body.min_clip_duration,
        max_clip_duration=body.max_clip_duration,
        channels_limit=body.channels_limit,
    )
    loop = asyncio.get_event_loop()
    job_manager.submit(job, run_job, loop)
    return _to_response(job)


@router.get("", response_model=list[JobResponse])
async def list_jobs():
    return [_to_response(j) for j in job_manager.all()]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):
    if not job_manager.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/{job_id}/clips", response_model=list[ClipResponse])
async def get_job_clips(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return [
        ClipResponse(
            **{k: v for k, v in clip.items() if k not in ("video_path", "thumbnail_path")},
            video_url=f"/api/clips/{clip['id']}/download",
            thumbnail_url=f"/api/clips/{clip['id']}/thumbnail",
        )
        for clip in job.clips
    ]
