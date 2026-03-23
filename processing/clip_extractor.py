from __future__ import annotations

from pathlib import Path

from core.schemas import CandidateMoment, FinalClip
from processing.video_montage import VideoMontage
from utils.ffmpeg_utils import capture_frame, cut_video_copy


class ClipExtractor:


    def __init__(self, config: dict, montage: VideoMontage, logger) -> None:
        self.config = config
        self.montage = montage
        self.logger = logger
        self.project_config = config.get("project", {})
        self.montage_config = config.get("montage", {})

    def export_clip(
        self,
        candidate: CandidateMoment,
        source_video: str,
        output_dir: str | Path,
        clip_index: int,
        has_audio: bool = True,
    ) -> FinalClip:
        output_dir = Path(output_dir)
        clips_dir = output_dir / "clips"
        thumbs_dir = output_dir / "thumbnails"
        raw_dir = output_dir / "raw_segments"
        temp_dir = output_dir / "tmp"

        for directory in (clips_dir, thumbs_dir, temp_dir):
            directory.mkdir(parents=True, exist_ok=True)
        if bool(self.montage_config.get("keep_raw_segments", True)):
            raw_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"clip_{clip_index:02d}"
        final_video_path = clips_dir / f"{base_name}.mp4"
        thumbnail_path = thumbs_dir / f"{base_name}.jpg"

        raw_segment_path = None
        if bool(self.montage_config.get("keep_raw_segments", True)):
            raw_segment_path = raw_dir / f"{base_name}_source.mp4"
            try:
                cut_video_copy(source_video, raw_segment_path, candidate.start, candidate.end)
            except Exception as exc:
                self.logger.warning("Raw clip copy failed for %s: %s", base_name, exc)
                raw_segment_path = None

        self.montage.render_clip(
            source_video=source_video,
            candidate=candidate,
            output_path=final_video_path,
            working_dir=temp_dir,
            has_audio=has_audio,
        )
        capture_frame(
            source_video,
            candidate.thumbnail_time or ((candidate.start + candidate.end) / 2.0),
            thumbnail_path,
        )

        return FinalClip(
            clip_id=clip_index,
            source_video=source_video,
            start=candidate.start,
            end=candidate.end,
            score=candidate.score,
            transcript=candidate.transcript,
            has_face=candidate.has_face,
            emotion=candidate.emotion,
            video_path=str(final_video_path),
            thumbnail_path=str(thumbnail_path),
            raw_segment_path=str(raw_segment_path) if raw_segment_path else None,
            metadata={
                "end_reason": candidate.end_reason,
                "primary_type": candidate.metadata.get("primary_type"),
                "source_title": candidate.metadata.get("source_title"),
                "duration": round(candidate.duration, 3),
            },
        )
