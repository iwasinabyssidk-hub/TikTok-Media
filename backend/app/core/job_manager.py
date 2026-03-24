from __future__ import annotations

import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class JobState:
    id: str
    status: str  # queued | running | completed | failed | cancelled
    channels: list[str]
    num_clips: int
    videos_per_channel: int
    min_clip_duration: float
    max_clip_duration: float
    channels_limit: int | None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: int = 0
    logs: list[str] = field(default_factory=list)
    clips: list[dict[str, Any]] = field(default_factory=list)
    report: dict[str, Any] | None = None
    error: str | None = None
    run_subdir: str | None = None
    future: Future | None = field(default=None, repr=False)
    cancel_requested: bool = False


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._executor = ThreadPoolExecutor(max_workers=1)

    def create(
        self,
        channels: list[str],
        num_clips: int,
        videos_per_channel: int,
        min_clip_duration: float,
        max_clip_duration: float,
        channels_limit: int | None,
    ) -> JobState:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = JobState(
            id=job_id,
            status="queued",
            channels=channels,
            num_clips=num_clips,
            videos_per_channel=videos_per_channel,
            min_clip_duration=min_clip_duration,
            max_clip_duration=max_clip_duration,
            channels_limit=channels_limit,
        )
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    def all(self) -> list[JobState]:
        return list(self._jobs.values())

    def delete(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status == "running":
            job.cancel_requested = True
        del self._jobs[job_id]
        return True

    def submit(self, job: JobState, fn, *args, **kwargs) -> None:
        future = self._executor.submit(fn, job, *args, **kwargs)
        job.future = future

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)


job_manager = JobManager()
