from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

from core.audio_analyzer import AudioAnalyzer
from core.face_analyzer import FaceAnalyzer
from core.motion_analyzer import MotionAnalyzer
from core.scene_detector import SceneDetector
from core.schemas import ChunkAnalysis, ChunkTask
from core.text_analyzer import TextAnalyzer
from utils.cache_manager import CacheManager
from utils.logger import get_logger

_WORKER_CONTEXT: dict = {}


def _init_worker(config: dict, cache_dir: str, log_file: str | None) -> None:
    logger = get_logger("chunk_worker", log_file=log_file)
    cache = CacheManager(cache_dir)
    _WORKER_CONTEXT["logger"] = logger
    _WORKER_CONTEXT["cache"] = cache
    _WORKER_CONTEXT["audio"] = AudioAnalyzer(config=config, cache=cache, logger=logger)
    _WORKER_CONTEXT["motion"] = MotionAnalyzer(config=config, logger=logger)
    _WORKER_CONTEXT["scene"] = SceneDetector(config=config, logger=logger)
    _WORKER_CONTEXT["face"] = FaceAnalyzer(config=config, logger=logger)
    _WORKER_CONTEXT["text"] = TextAnalyzer(config=config, logger=logger)
    _WORKER_CONTEXT["config"] = config


def _process_chunk(task_payload: dict) -> ChunkAnalysis:
    task = ChunkTask(**task_payload)
    config = _WORKER_CONTEXT["config"]
    cache: CacheManager = _WORKER_CONTEXT["cache"]
    logger = _WORKER_CONTEXT["logger"]
    stage_progress = bool(config.get("performance", {}).get("stage_progress", True))
    performance = config.get("performance", {})
    use_gpu_profile = bool(performance.get("use_gpu_whisper", True))
    skip_motion_on_cpu = (not use_gpu_profile) and bool(performance.get("skip_motion_on_cpu", True))
    skip_scene_on_cpu = (not use_gpu_profile) and bool(performance.get("skip_scene_on_cpu", True))

    cache_key = cache.build_key(
        "chunk_analysis",
        {
            "analysis_version": 4,
            "video": task.source_video,
            "visual_video": task.visual_video or task.source_video,
            "index": task.index,
            "start": round(task.start, 3),
            "end": round(task.end, 3),
            "whisper_model": config["performance"].get("whisper_model", "medium"),
            "use_gpu_whisper": config["performance"].get("use_gpu_whisper", True),
            "motion_step": config["performance"].get("motion_frame_step", 5),
            "cpu_motion_step": config["performance"].get("cpu_motion_frame_step", 5),
            "scene_step": config["performance"].get("scene_frame_step", 5),
            "cpu_scene_step": config["performance"].get("cpu_scene_frame_step", 5),
            "fast_cpu_visual_mode": config["performance"].get("fast_cpu_visual_mode", True),
            "motion_cpu_resize_width": config.get("motion", {}).get("cpu_resize_width", 224),
            "scene_cpu_resize_width": config.get("scenes", {}).get("cpu_resize_width", 224),
            "scene_cpu_resize_height": config.get("scenes", {}).get("cpu_resize_height", 126),
            "skip_motion_on_cpu": performance.get("skip_motion_on_cpu", True),
            "skip_scene_on_cpu": performance.get("skip_scene_on_cpu", True),
        },
    )
    if cache.exists(cache_key):
        if stage_progress:
            logger.info("Chunk %s | cache hit", task.index)
        return cache.load(cache_key)

    audio_analyzer: AudioAnalyzer = _WORKER_CONTEXT["audio"]
    motion_analyzer: MotionAnalyzer = _WORKER_CONTEXT["motion"]
    scene_detector: SceneDetector = _WORKER_CONTEXT["scene"]
    face_analyzer: FaceAnalyzer = _WORKER_CONTEXT["face"]
    text_analyzer: TextAnalyzer = _WORKER_CONTEXT["text"]

    audio_path = None
    audio_events = []
    audio_stats = {}
    text_segments = []
    text_events = []
    transcript_text = ""

    if stage_progress:
        logger.info("Chunk %s | started %.1fs-%.1fs", task.index, task.start, task.end)

    try:
        started = perf_counter()
        if stage_progress:
            logger.info("Chunk %s | extracting audio", task.index)
        audio_path = str(audio_analyzer.get_or_extract_audio(task.source_video, task))
        if stage_progress:
            logger.info("Chunk %s | audio extracted in %.1fs", task.index, perf_counter() - started)

        started = perf_counter()
        if stage_progress:
            logger.info("Chunk %s | audio analysis", task.index)
        audio_events, audio_stats = audio_analyzer.analyze(audio_path, task)
        if stage_progress:
            logger.info(
                "Chunk %s | audio analysis done in %.1fs (%s events)",
                task.index,
                perf_counter() - started,
                len(audio_events),
            )

        started = perf_counter()
        if stage_progress:
            logger.info("Chunk %s | whisper transcription", task.index)
        text_segments, text_events, transcript_text = text_analyzer.analyze(audio_path, task)
        if stage_progress:
            logger.info(
                "Chunk %s | whisper done in %.1fs (%s segments, %s events)",
                task.index,
                perf_counter() - started,
                len(text_segments),
                len(text_events),
            )
    except Exception as exc:
        logger.warning("Audio/text analysis failed for chunk %s: %s", task.index, exc)

    if skip_motion_on_cpu:
        if stage_progress:
            logger.info("Chunk %s | motion analysis skipped on CPU text-first mode", task.index)
        motion_events, motion_stats = [], {"skipped": True}
    else:
        try:
            started = perf_counter()
            if stage_progress:
                logger.info("Chunk %s | motion analysis", task.index)
            motion_events, motion_stats = motion_analyzer.analyze(task.visual_video or task.source_video, task)
            if stage_progress:
                logger.info(
                    "Chunk %s | motion analysis done in %.1fs (%s events)",
                    task.index,
                    perf_counter() - started,
                    len(motion_events),
                )
        except Exception as exc:
            logger.warning("Motion analysis failed for chunk %s: %s", task.index, exc)
            motion_events, motion_stats = [], {}

    if skip_scene_on_cpu:
        if stage_progress:
            logger.info("Chunk %s | scene analysis skipped on CPU text-first mode", task.index)
        scene_events, scene_stats = [], {"skipped": True}
    else:
        try:
            started = perf_counter()
            if stage_progress:
                logger.info("Chunk %s | scene analysis", task.index)
            scene_events, scene_stats = scene_detector.analyze(task.visual_video or task.source_video, task)
            if stage_progress:
                logger.info(
                    "Chunk %s | scene analysis done in %.1fs (%s events)",
                    task.index,
                    perf_counter() - started,
                    len(scene_events),
                )
        except Exception as exc:
            logger.warning("Scene analysis failed for chunk %s: %s", task.index, exc)
            scene_events, scene_stats = [], {}

    try:
        started = perf_counter()
        if stage_progress:
            logger.info("Chunk %s | face analysis", task.index)
        face_events, face_stats = face_analyzer.analyze(task.source_video, task)
        if stage_progress:
            logger.info(
                "Chunk %s | face analysis done in %.1fs (%s events)",
                task.index,
                perf_counter() - started,
                len(face_events),
            )
    except Exception as exc:
        logger.warning("Face analysis failed for chunk %s: %s", task.index, exc)
        face_events, face_stats = [], {}

    max_candidates_per_chunk = int(config["video_processing"].get("max_candidates_per_chunk", 25))
    result = ChunkAnalysis(
        task=task,
        audio_events=_trim_events(audio_events, max_candidates_per_chunk),
        motion_events=_trim_events(motion_events, max_candidates_per_chunk),
        scene_events=_trim_events(scene_events, max_candidates_per_chunk),
        face_events=_trim_events(face_events, max_candidates_per_chunk),
        text_events=_trim_events(text_events, max_candidates_per_chunk * 2),
        transcript_segments=text_segments,
        transcript_text=transcript_text,
        audio_path=audio_path,
        stats={
            "audio": audio_stats,
            "motion": motion_stats,
            "scene": scene_stats,
            "face": face_stats,
        },
    )
    cache.save(cache_key, result)
    if stage_progress:
        logger.info("Chunk %s | cached result", task.index)
    return result


def _trim_events(events, max_items: int):
    return sorted(events, key=lambda event: event.score, reverse=True)[:max_items]


class ChunkProcessor:


    def __init__(self, config: dict, cache_dir: str | Path, logger) -> None:
        self.config = config
        self.cache_dir = str(cache_dir)
        self.logger = logger
        self.performance_config = config.get("performance", {})

    def process_chunks(self, tasks: list[ChunkTask], log_file: str | None = None) -> list[ChunkAnalysis]:
        if not tasks:
            return []

        requested_workers = int(self.performance_config.get("parallel_workers", 4))
        if bool(self.performance_config.get("use_gpu_whisper", True)):
            requested_workers = min(
                requested_workers,
                int(self.performance_config.get("max_gpu_workers", 2)),
            )
        else:
            requested_workers = min(
                requested_workers,
                int(self.performance_config.get("max_cpu_workers", 1)),
            )
        workers = max(1, min(requested_workers, len(tasks)))

        task_payloads = [
            {
                "index": task.index,
                "start": task.start,
                "end": task.end,
                "source_video": task.source_video,
                "visual_video": task.visual_video,
            }
            for task in tasks
        ]

        if workers == 1:
            self.logger.info("Processing %s chunks with %s worker(s)", len(tasks), workers)
            _init_worker(self.config, self.cache_dir, log_file)
            return [_process_chunk(payload) for payload in task_payloads]

        self.logger.info("Processing %s chunks with %s worker(s)", len(tasks), workers)
        results: list[ChunkAnalysis] = []
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_init_worker,
            initargs=(self.config, self.cache_dir, log_file),
        ) as executor:
            future_map = {executor.submit(_process_chunk, payload): payload for payload in task_payloads}
            for future in as_completed(future_map):
                payload = future_map[future]
                result = future.result()
                self.logger.info(
                    "Chunk %s processed: %.1fs-%.1fs",
                    payload["index"],
                    payload["start"],
                    payload["end"],
                )
                results.append(result)

        results.sort(key=lambda item: item.task.index)
        return results
