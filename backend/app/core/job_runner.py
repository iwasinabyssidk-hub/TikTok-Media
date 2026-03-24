from __future__ import annotations

import asyncio
import copy
import logging
import logging.handlers
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

import yaml

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.core.ws_manager import ws_manager

# TTM logger names used across the pipeline
_TTM_LOGGER_NAMES = [
    "clip_detector",
    "chunk_worker",
    "highlight_extractor",
    "youtube_batch",
    "youtube_source",
    "video_montage",
    "clip_extractor",
    "audio_analyzer",
    "text_analyzer",
    "motion_analyzer",
    "scene_detector",
    "face_analyzer",
    "cache_manager",
]

_PROGRESS_PATTERNS = [
    ("Channel batch", 20),
    ("Downloading", 30),
    ("Processing chunk", 50),
    ("Ranking highlights", 70),
    ("Rendering clip", 80),
    ("clip_", 90),
    ("Batch complete", 100),
]


def _estimate_progress(message: str) -> int | None:
    for pattern, value in _PROGRESS_PATTERNS:
        if pattern.lower() in message.lower():
            return value
    return None


def _load_config() -> dict:
    config_path = _PROJECT_ROOT / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_job(job, loop: asyncio.AbstractEventLoop) -> None:
    """Runs the TTM pipeline in a background thread for the given job."""
    from app.core.job_manager import job_manager  # avoid circular

    job.status = "running"
    job.started_at = datetime.utcnow()
    job.progress = 0

    log_queue: queue.Queue = queue.Queue()

    # Custom handler that pushes records into our queue
    class _QueueHandler(logging.handlers.QueueHandler):
        def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
            return record

    q_handler = _QueueHandler(log_queue)
    q_handler.setLevel(logging.INFO)

    # Attach to all known TTM loggers
    attached: list[logging.Logger] = []
    for name in _TTM_LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.addHandler(q_handler)
        attached.append(logger)

    # Background thread: drain queue → job.logs + WebSocket
    stop_event = threading.Event()

    def _drain_logs():
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
        while not stop_event.is_set() or not log_queue.empty():
            try:
                record: logging.LogRecord = log_queue.get(timeout=0.1)
                line = formatter.format(record)
                job.logs.append(line)
                progress = _estimate_progress(record.getMessage())
                if progress and progress > job.progress:
                    job.progress = progress
                if not loop.is_closed():
                    ws_manager.broadcast_sync(
                        job.id,
                        {"type": "log", "level": record.levelname, "message": line},
                        loop,
                    )
                    if progress:
                        ws_manager.broadcast_sync(job.id, {"type": "progress", "value": job.progress}, loop)
            except queue.Empty:
                continue

    drain_thread = threading.Thread(target=_drain_logs, daemon=True)
    drain_thread.start()

    try:
        config = _load_config()

        # Apply job-level overrides
        config["video_processing"]["max_selected_clips_per_video"] = job.num_clips
        config["video_processing"]["min_clip_duration"] = job.min_clip_duration
        config["video_processing"]["max_clip_duration"] = job.max_clip_duration
        config["youtube"]["videos_per_channel"] = job.videos_per_channel

        from core.clip_detector import ClipDetector
        from processing.youtube_batch import YouTubeBatchProcessor
        from utils.logger import get_logger

        logger = get_logger("youtube_batch")

        detector = ClipDetector(config=config)
        batch = YouTubeBatchProcessor(config=config, detector=detector, logger=logger)

        result = batch.process_channels(
            channels=job.channels,
            max_channels=job.channels_limit,
            videos_per_channel=job.videos_per_channel,
        )

        if job.cancel_requested:
            job.status = "cancelled"
            return

        # Parse result into clips
        job.report = result
        job.run_subdir = result.get("run_subdir", "")
        clips = _extract_clips(result, job.id)
        job.clips = clips
        job.total_clips = len(clips)
        job.progress = 100
        job.status = "completed"

        ws_manager.broadcast_sync(job.id, {"type": "status", "status": "completed", "total_clips": job.total_clips}, loop)

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        ws_manager.broadcast_sync(job.id, {"type": "status", "status": "failed", "error": str(exc)}, loop)
    finally:
        stop_event.set()
        drain_thread.join(timeout=3)
        for logger in attached:
            logger.removeHandler(q_handler)
        job.completed_at = datetime.utcnow()


def _extract_clips(report: dict, job_id: str) -> list[dict]:
    clips: list[dict] = []
    clip_index = 1
    for channel_item in report.get("items", []):
        for video_item in channel_item.get("items", []):
            output_report = video_item.get("output_report") or {}
            for clip_data in output_report.get("clips", []):
                clip_id = f"clip_{job_id}_{clip_index:03d}"
                clips.append(
                    {
                        "id": clip_id,
                        "job_id": job_id,
                        "clip_index": clip_index,
                        "score": clip_data.get("score", 0.0),
                        "duration": clip_data.get("duration", 0.0),
                        "transcript": clip_data.get("transcript", ""),
                        "has_face": clip_data.get("has_face", False),
                        "emotion": clip_data.get("dominant_emotion"),
                        "primary_type": clip_data.get("primary_type", "hybrid"),
                        "tags": clip_data.get("tags", []),
                        "video_path": clip_data.get("video_path", ""),
                        "thumbnail_path": clip_data.get("thumbnail_path", ""),
                        "source_title": clip_data.get("source_title", ""),
                        "start_time": clip_data.get("start", 0.0),
                        "end_time": clip_data.get("end", 0.0),
                    }
                )
                clip_index += 1
    return clips
