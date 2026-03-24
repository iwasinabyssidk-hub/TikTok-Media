from __future__ import annotations

import re
from dataclasses import dataclass, field
from math import exp
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from utils.ffmpeg_utils import resolve_ffmpeg_binary


@dataclass(slots=True)
class YouTubeCandidate:
    video_id: str
    url: str
    title: str
    channel: str
    duration: int
    webpage_url: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DownloadedVideo:
    title: str
    query: str
    local_path: str
    source_url: str
    video_id: str
    duration: int
    channel: str
    metadata: dict[str, Any] = field(default_factory=dict)


class YouTubeSource:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.project_config = config.get("project", {})
        self.youtube_config = config.get("youtube", {})
        self.downloads_dir = Path(self.project_config.get("downloads_dir", ".downloads")) / "youtube"
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def find_candidates(self, query: str, search_options: dict[str, Any] | None = None) -> list[YouTubeCandidate]:
        max_results = int(
            self._resolve_option(
                "max_results",
                search_options,
                self.youtube_config.get("channel_search_max_results", 20),
            )
            or 20
        )
        search_prefix = str(
            self._resolve_option(
                "search_prefix",
                search_options,
                self.youtube_config.get("search_prefix", "ytsearch"),
            )
        )
        search_term = f"{search_prefix}{max_results}:{query}"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
            "ignoreerrors": True,
            "playlistend": max_results,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_term, download=False)
        except Exception as exc:
            self.logger.warning("YouTube search failed for '%s': %s", query, exc)
            return []

        entries = info.get("entries", []) if isinstance(info, dict) else []
        candidates = []
        for index, entry in enumerate(entries, start=1):
            if not entry:
                continue
            candidate = self._hydrate_candidate(
                entry=entry,
                search_rank=index,
                query=query,
                search_options=search_options,
            )
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates

    def build_channel_profile(self, channel_ref: str) -> tuple[str, dict[str, Any]]:
        query = self._channel_query(channel_ref)
        keywords = self._channel_keywords(channel_ref)
        profile = {
            "required_channel_keywords": keywords,
            "preferred_channel_keywords": keywords,
            "min_duration_seconds": int(self.youtube_config.get("channel_min_duration_seconds", 300)),
            "max_duration_seconds": int(self.youtube_config.get("channel_max_duration_seconds", 10800)),
            "generic_query_target_minutes": float(self.youtube_config.get("channel_query_target_minutes", 28)),
            "generic_query_duration_spread": float(self.youtube_config.get("channel_query_duration_spread", 22)),
            "max_results": int(self.youtube_config.get("channel_search_max_results", 20)),
        }
        return query, profile

    def download_candidate(self, candidate: YouTubeCandidate, title: str) -> DownloadedVideo:
        target_dir = self.downloads_dir / self._safe_stem(title)
        target_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(target_dir / "%(id)s.%(ext)s")
        ffmpeg_path = resolve_ffmpeg_binary("ffmpeg")
        target_height = int(self.youtube_config.get("target_height", 1080))
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "windowsfilenames": True,
            "noplaylist": True,
            "overwrites": True,
            "writesubtitles": bool(self.youtube_config.get("download_subtitles", False)),
            "writeautomaticsub": bool(self.youtube_config.get("download_subtitles", False)),
            "writeinfojson": bool(self.youtube_config.get("write_info_json", True)),
            "subtitleslangs": ["ru", "ru-orig", "en", "en-orig"],
            "ignoreerrors": False,
            "retries": 10,
            "fragment_retries": 10,
            "http_chunk_size": 10485760,
            "legacy_server_connect": True,
        }
        if ffmpeg_path and ffmpeg_path != "ffmpeg":
            ydl_opts["ffmpeg_location"] = ffmpeg_path
            ydl_opts["format"] = (
                f"bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]"
                f"/bestvideo[height<={target_height}]+bestaudio"
                f"/best[height<={target_height}][ext=mp4]"
                f"/best[height<={target_height}]"
                "/best"
            )
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = (
                f"best[height<={target_height}][ext=mp4][vcodec!=none][acodec!=none]"
                f"/best*[height<={target_height}][vcodec!=none][acodec!=none]"
                "/best"
            )

        with YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(candidate.webpage_url, download=True)
            prepared = ydl.prepare_filename(result)

        local_path = Path(prepared)
        if not local_path.exists():
            alternatives = sorted(target_dir.glob(f"{candidate.video_id}.*"))
            media_files = [path for path in alternatives if path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
            if media_files:
                local_path = media_files[0]
            elif alternatives:
                local_path = alternatives[0]

        return DownloadedVideo(
            title=title,
            query=str(candidate.metadata.get("query") or ""),
            local_path=str(local_path.resolve()),
            source_url=candidate.webpage_url,
            video_id=candidate.video_id,
            duration=candidate.duration,
            channel=candidate.channel,
            metadata={
                "candidate_score": round(candidate.score, 3),
                "yt_title": candidate.title,
                "channel": candidate.channel,
            },
        )

    def _hydrate_candidate(
        self,
        entry: dict[str, Any],
        search_rank: int,
        query: str,
        search_options: dict[str, Any] | None,
    ) -> YouTubeCandidate | None:
        video_id = str(entry.get("id") or "")
        if not video_id:
            return None

        title = str(entry.get("title") or "")
        duration = int(entry.get("duration") or 0)
        webpage_url = str(entry.get("url") or entry.get("webpage_url") or "")
        if webpage_url and not webpage_url.startswith("http"):
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
        if not webpage_url:
            return None

        min_duration = int(self._resolve_option("min_duration_seconds", search_options, 300) or 0)
        max_duration = int(self._resolve_option("max_duration_seconds", search_options, 0) or 0)
        if duration < min_duration:
            return None
        if max_duration > 0 and duration > max_duration:
            return None
        if entry.get("live_status") in {"is_live", "is_upcoming"}:
            return None

        channel = str(entry.get("channel") or entry.get("uploader") or "")
        required_channel_keywords = self._keyword_list(search_options, "required_channel_keywords")
        if required_channel_keywords and not any(keyword in channel.lower() for keyword in required_channel_keywords):
            return None

        score = self._score_candidate(
            query=query,
            search_rank=search_rank,
            title=title,
            channel=channel,
            duration=duration,
            description=str(entry.get("description") or ""),
            language=str(entry.get("language") or ""),
            search_options=search_options,
        )
        if score <= 0:
            return None

        return YouTubeCandidate(
            video_id=video_id,
            url=webpage_url,
            title=title,
            channel=channel,
            duration=duration,
            webpage_url=webpage_url,
            score=score,
            metadata={
                "language": entry.get("language"),
                "description": entry.get("description"),
                "search_rank": search_rank,
                "query": query,
            },
        )

    def _score_candidate(
        self,
        query: str,
        search_rank: int,
        title: str,
        channel: str,
        duration: int,
        description: str,
        language: str,
        search_options: dict[str, Any] | None,
    ) -> float:
        title_lower = title.lower()
        channel_lower = channel.lower()
        description_lower = description.lower()
        prefer_keywords = self._merged_keywords("prefer_keywords", search_options)
        avoid_keywords = self._merged_keywords("avoid_keywords", search_options)
        clickbait_keywords = self._merged_keywords("clickbait_keywords", search_options)
        preferred_channels = self._merged_keywords("preferred_channel_keywords", search_options)
        required_channel_keywords = self._keyword_list(search_options, "required_channel_keywords")
        language_priority = [word.lower() for word in self.youtube_config.get("language_priority", [])]

        score = 12.0
        score += max(0.0, 26.0 - (search_rank - 1) * 2.1)
        score += self._duration_fit_score(duration, search_options)

        if required_channel_keywords:
            if any(keyword in channel_lower for keyword in required_channel_keywords):
                score += 34.0
            else:
                return -1.0

        if self._looks_like_series(title):
            score -= 24.0
        if self._is_clickbait_title(title):
            score -= 18.0

        uppercase_ratio = self._uppercase_ratio(title)
        if uppercase_ratio > 0.58:
            score -= 14.0
        elif uppercase_ratio > 0.40:
            score -= 8.0

        if len(title) > 110:
            score -= 10.0
        elif len(title) > 85:
            score -= 5.0

        for keyword in clickbait_keywords:
            if keyword in title_lower or keyword in description_lower:
                score -= 10.0
        for keyword in avoid_keywords:
            if keyword in title_lower or keyword in description_lower:
                score -= 18.0
        if any(keyword in title_lower for keyword in prefer_keywords):
            score += 6.0
        if any(keyword in description_lower for keyword in prefer_keywords):
            score += 3.0
        if any(keyword in channel_lower for keyword in preferred_channels):
            score += 12.0

        if language:
            language_lower = language.lower()
            if language_lower in language_priority:
                score += 4.0

        query_tokens = self._significant_tokens(query)
        title_tokens = self._significant_tokens(title)
        channel_tokens = self._significant_tokens(channel)
        overlap = len(query_tokens & (title_tokens | channel_tokens))
        score += min(12.0, overlap * 2.5)
        return score

    def _duration_fit_score(self, duration_seconds: int, search_options: dict[str, Any] | None = None) -> float:
        target_minutes = float(self._resolve_option("generic_query_target_minutes", search_options, 28))
        spread_minutes = float(self._resolve_option("generic_query_duration_spread", search_options, 22))
        minutes = duration_seconds / 60.0
        exponent = -((minutes - target_minutes) ** 2) / (2 * (spread_minutes**2))
        return 18.0 * exp(exponent)

    def _resolve_option(self, key: str, search_options: dict[str, Any] | None, default: Any) -> Any:
        if search_options and key in search_options and search_options.get(key) is not None:
            return search_options.get(key)
        return self.youtube_config.get(key, default)

    def _channel_query(self, channel_ref: str) -> str:
        cleaned = channel_ref.strip()
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            parsed = urlparse(cleaned)
            parts = [part for part in parsed.path.split("/") if part]
            if parts:
                tail = parts[-1]
                return tail if tail.startswith("@") else tail.replace("-", " ").replace("_", " ")
        return cleaned

    def _channel_keywords(self, channel_ref: str) -> list[str]:
        cleaned = self._channel_query(channel_ref).lower().replace("@", " ")
        tokens = [
            token
            for token in re.findall(r"\w+", cleaned, flags=re.IGNORECASE | re.UNICODE)
            if len(token) >= 3 and token not in {"youtube", "channel", "official", "profile"}
        ]
        return list(dict.fromkeys(tokens[:4]))

    def _merged_keywords(self, base_key: str, search_options: dict[str, Any] | None = None) -> list[str]:
        values = [str(word).lower() for word in self.youtube_config.get(base_key, []) if str(word).strip()]
        if search_options:
            values.extend(self._keyword_list(search_options, base_key))
        return list(dict.fromkeys(values))

    @staticmethod
    def _keyword_list(source: dict[str, Any] | None, key: str) -> list[str]:
        if not source:
            return []
        return [str(word).lower() for word in source.get(key, []) if str(word).strip()]

    @staticmethod
    def _uppercase_ratio(text: str) -> float:
        letters = [char for char in text if char.isalpha()]
        if not letters:
            return 0.0
        uppercase = sum(1 for char in letters if char.isupper())
        return uppercase / len(letters)

    @staticmethod
    def _looks_like_series(text: str) -> bool:
        lowered = text.lower()
        series_markers = ("season", "episode", "ep.", "part ", "pt.")
        if any(marker in lowered for marker in series_markers):
            return True
        return bool(re.search(r"\b(?:ep|part|pt)\s*\d+\b", lowered, flags=re.UNICODE))

    @staticmethod
    def _is_clickbait_title(text: str) -> bool:
        lowered = text.lower()
        markers = (
            "watch until the end",
            "you will not believe",
            "mind blowing",
            "shocking",
            "crazy ending",
            "must watch",
        )
        return any(marker in lowered for marker in markers) or text.count("!") >= 3

    @staticmethod
    def _safe_stem(value: str) -> str:
        return re.sub(r"[^\w\-\. ]+", "_", value, flags=re.UNICODE).strip(" ._") or "video"

    @staticmethod
    def _significant_tokens(value: str) -> set[str]:
        stopwords = {
            "the",
            "a",
            "an",
            "of",
            "to",
            "for",
            "and",
            "with",
            "from",
            "video",
            "official",
            "channel",
        }
        tokens = set(re.findall(r"\w+", value.lower(), flags=re.UNICODE))
        return {token for token in tokens if len(token) >= 3 and token not in stopwords}
