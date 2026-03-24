from __future__ import annotations

from pydantic import BaseModel


class ClipResponse(BaseModel):
    id: str
    job_id: str
    clip_index: int
    score: float
    duration: float
    transcript: str
    has_face: bool
    emotion: str | None = None
    primary_type: str
    tags: list[str] = []
    video_url: str
    thumbnail_url: str
    source_title: str
    start_time: float
    end_time: float
