from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class VideoMetadata:
    path: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    sample_rate: int = 0


@dataclass(slots=True)
class ChunkTask:
    index: int
    start: float
    end: float
    source_video: str
    visual_video: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(slots=True)
class PeakEvent:
    time: float
    score: float
    label: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WordTiming:
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: list[WordTiming] = field(default_factory=list)
    emotional_weight: float = 0.0
    is_question: bool = False
    is_exclamation: bool = False
    punchline_score: float = 0.0
    tags: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(slots=True)
class CandidateMoment:
    candidate_id: str
    start: float
    end: float
    anchor_time: float
    chunk_index: int
    score: float = 0.0
    transcript: str = ""
    transcript_words: list[WordTiming] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    modalities: dict[str, float] = field(default_factory=dict)
    source_labels: list[str] = field(default_factory=list)
    has_face: bool = False
    emotion: str | None = None
    face_score: float = 0.0
    audio_peak: float = 0.0
    motion_peak: float = 0.0
    text_score: float = 0.0
    scene_change_count: int = 0
    length_score: float = 0.0
    thumbnail_time: float | None = None
    end_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(slots=True)
class ChunkAnalysis:
    task: ChunkTask
    audio_events: list[PeakEvent] = field(default_factory=list)
    motion_events: list[PeakEvent] = field(default_factory=list)
    scene_events: list[PeakEvent] = field(default_factory=list)
    face_events: list[PeakEvent] = field(default_factory=list)
    text_events: list[PeakEvent] = field(default_factory=list)
    transcript_segments: list[TranscriptSegment] = field(default_factory=list)
    transcript_text: str = ""
    audio_path: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FinalClip:
    clip_id: int
    source_video: str
    start: float
    end: float
    score: float
    transcript: str
    has_face: bool
    emotion: str | None
    video_path: str = ""
    thumbnail_path: str = ""
    raw_segment_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_report_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.clip_id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "start_time": round(self.start, 3),
            "end_time": round(self.end, 3),
            "score": round(self.score, 2),
            "text": self.transcript,
            "transcript": self.transcript,
            "has_face": self.has_face,
            "emotion": self.emotion,
            "video_path": self.video_path,
            "thumbnail_path": self.thumbnail_path,
        }
        payload.update(self.metadata)
        return payload


def ensure_path(path: str | Path) -> Path:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved
