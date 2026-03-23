from __future__ import annotations

import json
import re
from pathlib import Path

from core.schemas import ChunkTask, VideoMetadata
from core.scorer import HighlightScorer
from processing.chunk_processor import ChunkProcessor
from processing.clip_extractor import ClipExtractor
from processing.video_montage import VideoMontage
from utils.cache_manager import CacheManager
from utils.ffmpeg_utils import build_visual_proxy, probe_video
from utils.logger import get_logger
from core.text_analyzer import TextAnalyzer


class ClipDetector:


    def __init__(self, config: dict) -> None:
        self.config = config
        self.project_config = config.get("project", {})
        self.output_base = Path(self.project_config.get("output_dir", "output"))
        self.output_base.mkdir(parents=True, exist_ok=True)
        self.log_path = self.output_base / "pipeline.log"

        self.logger = get_logger("clip_detector", log_file=str(self.log_path))
        self.cache = CacheManager(self.project_config.get("cache_dir", ".cache"))
        self.chunk_processor = ChunkProcessor(
            config=config,
            cache_dir=self.project_config.get("cache_dir", ".cache"),
            logger=self.logger,
        )
        self.scorer = HighlightScorer(config=config, logger=self.logger)
        self.montage = VideoMontage(config=config, logger=self.logger)
        self.extractor = ClipExtractor(config=config, montage=self.montage, logger=self.logger)

    def run(
        self,
        video_path: str,
        run_subdir: str | None = None,
        output_slug: str | None = None,
        source_title: str | None = None,
    ) -> dict:
        source_video = Path(video_path).resolve()
        metadata = self._probe_metadata(source_video)
        resolved_source_title = source_title or output_slug or source_video.stem
        target_name = self._safe_name(output_slug or source_video.stem)
        target_dir = self.output_base / target_name
        if run_subdir:
            target_dir = self.output_base / run_subdir / target_name
        target_dir.mkdir(parents=True, exist_ok=True)

        if bool(self.config.get("performance", {}).get("preload_whisper", True)):
            try:
                TextAnalyzer(config=self.config, logger=self.logger).warmup()
            except Exception as exc:
                self.logger.warning("Whisper warmup failed, continuing with lazy loading: %s", exc)

        if not bool(self.config.get("performance", {}).get("use_gpu_whisper", True)) and bool(
            self.config.get("performance", {}).get("fast_cpu_visual_mode", True)
        ):
            self.logger.info("CPU fast visual mode enabled: lightweight motion and scene analysis")
        if not bool(self.config.get("performance", {}).get("use_gpu_whisper", True)) and bool(
            self.config.get("performance", {}).get("cpu_text_first_mode", True)
        ):
            self.logger.info("CPU text-first mode enabled: subtitle/audio ranking is prioritized")

        performance = self.config.get("performance", {})
        skip_visual = (
            not bool(performance.get("use_gpu_whisper", True))
            and bool(performance.get("skip_motion_on_cpu", True))
            and bool(performance.get("skip_scene_on_cpu", True))
        )
        visual_source = source_video if skip_visual else self._prepare_visual_source(source_video)
        self.logger.info("Preparing chunk list for %s", source_video.name)
        chunk_tasks = self._build_chunks(source_video, metadata.duration, visual_source=visual_source)
        chunk_results = self.chunk_processor.process_chunks(chunk_tasks, log_file=str(self.log_path))
        self.logger.info("Finished chunk analysis. Building ranked highlight list.")
        selected = self.scorer.select_highlights(chunk_results, metadata.duration)

        final_clips = []
        for clip_index, candidate in enumerate(selected, start=1):
            candidate.metadata["source_title"] = resolved_source_title
            self.logger.info(
                "Rendering clip %s/%s: %.2fs -> %.2fs (score %.2f)",
                clip_index,
                len(selected),
                candidate.start,
                candidate.end,
                candidate.score,
            )
            final_clips.append(
                self.extractor.export_clip(
                    candidate=candidate,
                    source_video=str(source_video),
                    output_dir=target_dir,
                    clip_index=clip_index,
                    has_audio=metadata.has_audio,
                )
            )
            self.logger.info("Saved clip %s/%s to %s", clip_index, len(selected), final_clips[-1].video_path)

        report = self._build_report(metadata=metadata, clips=final_clips)
        report_path = target_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.logger.info("Saved report to %s", report_path)
        return report

    def _build_chunks(self, source_video: Path, duration: float, visual_source: Path | None = None) -> list[ChunkTask]:
        performance = self.config.get("performance", {})
        if bool(performance.get("use_gpu_whisper", True)):
            chunk_duration = float(performance.get("chunk_duration", 300))
        else:
            chunk_duration = float(performance.get("cpu_chunk_duration", performance.get("chunk_duration", 300)))
        tasks = []
        chunk_index = 0
        start = 0.0
        while start < duration:
            end = min(duration, start + chunk_duration)
            tasks.append(
                ChunkTask(
                    index=chunk_index,
                    start=start,
                    end=end,
                    source_video=str(source_video),
                    visual_video=str((visual_source or source_video).resolve()),
                )
            )
            chunk_index += 1
            start = end
        return tasks

    def _prepare_visual_source(self, source_video: Path) -> Path:
        performance = self.config.get("performance", {})
        if bool(performance.get("use_gpu_whisper", True)):
            return source_video
        if not bool(performance.get("fast_cpu_visual_mode", True)):
            return source_video
        if not bool(performance.get("use_visual_proxy_on_cpu", True)):
            return source_video

        motion_cfg = self.config.get("motion", {})
        scenes_cfg = self.config.get("scenes", {})
        width = max(
            int(motion_cfg.get("cpu_resize_width", motion_cfg.get("resize_width", 160))),
            int(scenes_cfg.get("cpu_resize_width", scenes_cfg.get("resize_width", 160))),
        )
        height = int(scenes_cfg.get("cpu_resize_height", scenes_cfg.get("resize_height", 90)))
        fps = float(performance.get("cpu_visual_proxy_fps", 2.0))
        crf = int(performance.get("cpu_visual_proxy_crf", 38))

        key = self.cache.build_key(
            "visual_proxy",
            {
                "video": str(source_video),
                "mtime_ns": source_video.stat().st_mtime_ns,
                "size": source_video.stat().st_size,
                "fps": fps,
                "width": width,
                "height": height,
                "crf": crf,
            },
        )
        proxy_path = self.cache.resolve_path("visual_proxy", f"{key}.mp4")
        if proxy_path.exists():
            try:
                proxy_meta = probe_video(proxy_path)
                if float(proxy_meta.get("duration", 0.0) or 0.0) > 0 and int(proxy_meta.get("width", 0) or 0) > 0:
                    self.logger.info("Using cached visual proxy: %s", proxy_path.name)
                    return proxy_path.resolve()
            except Exception:
                pass
            self.logger.warning("Cached visual proxy is invalid, rebuilding: %s", proxy_path.name)
            try:
                proxy_path.unlink(missing_ok=True)
            except Exception:
                pass

        self.logger.info(
            "Building visual proxy for CPU analysis: %ss, %sx%s",
            f"{fps:g}fps",
            width,
            height,
        )
        try:
            return build_visual_proxy(
                video_path=source_video,
                proxy_path=proxy_path,
                fps=fps,
                width=width,
                height=height,
                crf=crf,
            ).resolve()
        except Exception as exc:
            self.logger.warning("Visual proxy build failed, falling back to source video: %s", exc)
            return source_video

    @staticmethod
    def _probe_metadata(video_path: Path) -> VideoMetadata:
        probed = probe_video(video_path)
        return VideoMetadata(
            path=str(video_path),
            duration=float(probed["duration"]),
            width=int(probed["width"]),
            height=int(probed["height"]),
            fps=float(probed["fps"]),
            has_audio=bool(probed["has_audio"]),
            sample_rate=int(probed.get("sample_rate", 0)),
        )

    @staticmethod
    def _build_report(metadata: VideoMetadata, clips) -> dict:
        total_duration_output = round(sum(clip.duration for clip in clips), 3)
        return {
            "source_video": metadata.path,
            "duration_original": round(metadata.duration, 3),
            "total_clips": len(clips),
            "total_duration_output": total_duration_output,
            "clips": [clip.to_report_dict() for clip in clips],
        }

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^\w\-. ]+", "_", value, flags=re.UNICODE).strip(" ._")
        return cleaned or "video"
