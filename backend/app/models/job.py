from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    channels: list[str] = Field(..., min_length=1)
    num_clips: int = Field(1, ge=1, le=20)
    videos_per_channel: int = Field(2, ge=1, le=20)
    min_clip_duration: float = Field(40.0, ge=10.0, le=300.0)
    max_clip_duration: float = Field(65.0, ge=10.0, le=300.0)
    channels_limit: int | None = Field(None, ge=1)


class JobResponse(BaseModel):
    id: str
    status: str
    progress: int
    channels: list[str]
    num_clips: int
    videos_per_channel: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_clips: int = 0
    error: str | None = None
    run_subdir: str | None = None
    logs: list[str] = Field(default_factory=list)
    report: dict[str, Any] | None = None
