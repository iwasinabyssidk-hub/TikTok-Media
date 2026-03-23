from __future__ import annotations

import json
import random
import re
from datetime import datetime
from pathlib import Path

from core.clip_detector import ClipDetector
from utils.youtube_utils import YouTubeSource


class YouTubeBatchProcessor:
    def __init__(self, config: dict, detector: ClipDetector, logger) -> None:
        self.config = config
        self.detector = detector
        self.logger = logger
        self.project_config = config.get("project", {})
        self.youtube_config = config.get("youtube", {})
        self.output_dir = Path(self.project_config.get("output_dir", "output"))
        self.source = YouTubeSource(config=config, logger=logger)
        self.rng = random.Random(self.youtube_config.get("random_seed"))

    def process_channels(
        self,
        channels: list[str],
        max_channels: int | None = None,
        videos_per_channel: int | dict[str, int] | None = None,
    ) -> dict:
        run_subdir = self._allocate_run_subdir("channels")
        configured_limit = int(self.youtube_config.get("videos_per_channel", 2) or 2)
        prepared_channels = [channel.strip() for channel in channels if channel.strip()]
        prepared_channels = self._randomize_channels(prepared_channels)
        if max_channels and max_channels > 0:
            prepared_channels = prepared_channels[:max_channels]

        default_limit = configured_limit
        channel_limits: dict[str, int] = {}
        if isinstance(videos_per_channel, dict):
            channel_limits = {str(key): max(0, int(value)) for key, value in videos_per_channel.items()}
        elif videos_per_channel is not None and videos_per_channel > 0:
            default_limit = int(videos_per_channel)

        items = []
        processed_videos = 0
        seen_video_ids: set[str] = set()

        for channel_index, channel_ref in enumerate(prepared_channels, start=1):
            current_limit = channel_limits.get(channel_ref, default_limit)
            if current_limit <= 0:
                items.append(
                    {
                        "channel": channel_ref,
                        "status": "skipped",
                        "requested_videos": current_limit,
                        "items": [],
                    }
                )
                continue

            self.logger.info("Channel batch %s/%s: %s", channel_index, len(prepared_channels), channel_ref)
            query, profile = self.source.build_channel_profile(channel_ref)
            candidates = self.source.find_candidates(query=query, search_options=profile)
            if not candidates:
                items.append(
                    {
                        "channel": channel_ref,
                        "status": "not_found",
                        "requested_videos": current_limit,
                        "items": [],
                    }
                )
                continue

            candidates = self._randomize_candidates(candidates, selection_limit=current_limit)
            used_for_channel = 0
            channel_results = []

            for candidate in candidates:
                if candidate.video_id in seen_video_ids:
                    continue
                if used_for_channel >= current_limit:
                    break

                display_title = candidate.title
                try:
                    downloaded = self.source.download_candidate(candidate, f"{channel_ref} - {display_title}")
                    clip_report = self.detector.run(
                        downloaded.local_path,
                        run_subdir=str(Path(run_subdir) / self._safe_segment(channel_ref)),
                        output_slug=display_title,
                        source_title=display_title,
                    )
                    channel_results.append(
                        {
                            "title": display_title,
                            "status": "processed",
                            "downloaded_video": downloaded.local_path,
                            "source_url": downloaded.source_url,
                            "channel": downloaded.channel,
                            "duration_seconds": downloaded.duration,
                            "output_report": clip_report,
                        }
                    )
                    seen_video_ids.add(candidate.video_id)
                    processed_videos += 1
                    used_for_channel += 1
                except Exception as exc:
                    self.logger.exception(
                        "Failed processing channel '%s' candidate '%s': %s",
                        channel_ref,
                        display_title,
                        exc,
                    )
                    channel_results.append(
                        {
                            "title": display_title,
                            "status": "failed",
                            "error": str(exc),
                        }
                    )

            items.append(
                {
                    "channel": channel_ref,
                    "query": query,
                    "requested_videos": current_limit,
                    "processed_videos": used_for_channel,
                    "items": channel_results,
                }
            )

        report = {
            "mode": "youtube_channels",
            "total_requested_channels": len(prepared_channels),
            "videos_per_channel": default_limit,
            "channel_limits": channel_limits,
            "processed_videos": processed_videos,
            "run_subdir": run_subdir,
            "items": items,
        }
        batch_report = self.output_dir / run_subdir / "youtube_batch_report.json"
        batch_report.parent.mkdir(parents=True, exist_ok=True)
        batch_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def _allocate_run_subdir(self, prefix: str) -> str:
        date_suffix = datetime.now().strftime("%m-%d")
        sanitized_prefix = re.sub(r"[^\w\-]+", "", prefix.lower(), flags=re.UNICODE) or "run"
        index = 1
        while True:
            candidate = f"{sanitized_prefix}{index}_{date_suffix}"
            if not (self.output_dir / candidate).exists():
                return candidate
            index += 1

    @staticmethod
    def _safe_segment(value: str) -> str:
        return re.sub(r"[^\w\-\. ]+", "_", value, flags=re.UNICODE).strip(" ._") or "channel"

    def _randomize_channels(self, channels: list[str]) -> list[str]:
        if not bool(self.youtube_config.get("randomize_channel_order", True)):
            return channels
        randomized = channels.copy()
        self.rng.shuffle(randomized)
        return randomized

    def _randomize_candidates(self, candidates: list, selection_limit: int) -> list:
        if not bool(self.youtube_config.get("randomize_video_order", True)):
            return candidates
        if len(candidates) <= 1:
            return candidates

        multiplier = int(self.youtube_config.get("random_candidate_pool_multiplier", 4) or 4)
        min_pool = int(self.youtube_config.get("random_candidate_pool_min_size", 8) or 8)
        pool_size = min(len(candidates), max(selection_limit * multiplier, min_pool))
        if pool_size <= 1:
            return candidates

        randomized_pool = self._weighted_shuffle(candidates[:pool_size])
        return randomized_pool + candidates[pool_size:]

    def _weighted_shuffle(self, candidates: list) -> list:
        pool = list(candidates)
        ordered = []
        while pool:
            weights = [max(float(getattr(candidate, "score", 0.0) or 0.0), 0.1) for candidate in pool]
            total_weight = sum(weights)
            threshold = self.rng.random() * total_weight
            running = 0.0
            chosen_index = len(pool) - 1
            for index, weight in enumerate(weights):
                running += weight
                if running >= threshold:
                    chosen_index = index
                    break
            ordered.append(pool.pop(chosen_index))
        return ordered
