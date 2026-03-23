from __future__ import annotations

import math
import re
from collections import Counter

from core.schemas import CandidateMoment, ChunkAnalysis, PeakEvent, TranscriptSegment, WordTiming
from utils.ffmpeg_utils import clamp, gaussian_score


class HighlightScorer:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.video_config = config.get("video_processing", {})
        self.weights = config.get("scoring_weights", {})
        self.cliffhanger = config.get("cliffhanger", {})

    def select_highlights(self, chunks: list[ChunkAnalysis], video_duration: float) -> list[CandidateMoment]:
        if not chunks:
            return []

        candidates = self._build_candidates(chunks=chunks, video_duration=video_duration)
        if not candidates:
            return []

        for candidate in candidates:
            candidate.score = self._score_candidate(candidate)
            candidate.thumbnail_time = candidate.start + candidate.duration * float(
                self.video_config.get("thumbnail_offset_ratio", 0.4)
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        selected = self._select_with_diversity(candidates, video_duration)
        selected.sort(key=lambda item: item.score, reverse=True)

        transcript_segments = [segment for chunk in chunks for segment in chunk.transcript_segments]
        motion_events = [event for chunk in chunks for event in chunk.motion_events]
        scene_events = [event for chunk in chunks for event in chunk.scene_events]
        text_events = [event for chunk in chunks for event in chunk.text_events]

        for candidate in selected:
            self._refine_boundaries(
                candidate=candidate,
                transcript_segments=transcript_segments,
                motion_events=motion_events,
                scene_events=scene_events,
                text_events=text_events,
                video_duration=video_duration,
            )

        max_selected = int(self.video_config.get("max_selected_clips_per_video", 0) or 0)
        if max_selected > 0:
            selected.sort(key=lambda item: item.score, reverse=True)
            selected = selected[:max_selected]

        return selected

    def _build_candidates(self, chunks: list[ChunkAnalysis], video_duration: float) -> list[CandidateMoment]:
        anchors = []
        for chunk in chunks:
            for event in (
                chunk.audio_events
                + chunk.motion_events
                + chunk.scene_events
                + chunk.face_events
                + chunk.text_events
            ):
                if event.score < 0.18:
                    continue
                anchors.append(
                    {
                        "time": event.time,
                        "event": event,
                        "chunk_index": chunk.task.index,
                        "chunk": chunk,
                    }
                )

        if not anchors:
            return []

        anchors.sort(key=lambda item: item["time"])
        merge_window = float(self.video_config.get("anchor_merge_window", 2.5))
        clusters: list[list[dict]] = []
        for anchor in anchors:
            if not clusters or anchor["time"] - clusters[-1][-1]["time"] > merge_window:
                clusters.append([anchor])
            else:
                clusters[-1].append(anchor)

        candidates: list[CandidateMoment] = []
        min_duration = float(self.video_config.get("min_clip_duration", 8))
        max_duration = float(self.video_config.get("max_clip_duration", 18))
        anticipation = float(self.video_config.get("anticipation_seconds", 2.8))
        payoff = float(self.video_config.get("payoff_seconds", 8.0))

        for cluster_index, cluster in enumerate(clusters):
            anchor_time = sum(item["time"] * max(item["event"].score, 0.1) for item in cluster) / sum(
                max(item["event"].score, 0.1) for item in cluster
            )
            chunk = cluster[0]["chunk"]
            labels = [item["event"].label for item in cluster]
            start = max(0.0, anchor_time - anticipation)
            end = min(video_duration, anchor_time + payoff)

            if any(label in {"quiet_loud_payoff", "scene_start", "scene_cut"} for label in labels):
                start = max(0.0, start - 1.0)
            if any(label in {"punchline", "intriguing_question"} for label in labels):
                end = min(video_duration, end + 1.2)

            overlapping_segments = [
                segment
                for segment in chunk.transcript_segments
                if not (segment.end < start - 1.2 or segment.start > end + 1.2)
            ]
            if overlapping_segments:
                start = min(start, min(segment.start for segment in overlapping_segments) - 0.2)
                end = max(end, max(segment.end for segment in overlapping_segments) + 0.25)

            duration = end - start
            if duration < min_duration:
                pad = (min_duration - duration) / 2.0
                start = max(0.0, start - pad)
                end = min(video_duration, end + pad)
            if end - start > max_duration:
                if overlapping_segments:
                    first = overlapping_segments[0].start
                    last = overlapping_segments[-1].end
                    compact_start = max(0.0, min(first - 0.6, anchor_time - max_duration / 2.0))
                    compact_end = min(video_duration, max(last + 0.4, compact_start + min_duration))
                    if compact_end - compact_start <= max_duration + 0.6:
                        start, end = compact_start, compact_end
                if end - start > max_duration:
                    start = max(0.0, anchor_time - max_duration * 0.45)
                    end = min(video_duration, start + max_duration)

            candidate = CandidateMoment(
                candidate_id=f"cand_{cluster_index:04d}",
                start=start,
                end=end,
                anchor_time=anchor_time,
                chunk_index=chunk.task.index,
                source_labels=list(dict.fromkeys(labels)),
            )
            self._hydrate_candidate(candidate, chunks)
            if candidate.duration >= min_duration * 0.85:
                candidates.append(candidate)

        subtitle_candidates = self._build_subtitle_candidates(
            chunks=chunks,
            video_duration=video_duration,
            start_index=len(candidates),
        )
        candidates.extend(subtitle_candidates)
        return candidates

    def _hydrate_candidate(self, candidate: CandidateMoment, chunks: list[ChunkAnalysis]) -> None:
        audio_events = []
        motion_events = []
        scene_events = []
        face_events = []
        text_events = []
        transcript_segments = []

        for chunk in chunks:
            if chunk.task.end < candidate.start - 1.5 or chunk.task.start > candidate.end + 1.5:
                continue
            audio_events.extend(self._inside(chunk.audio_events, candidate.start, candidate.end))
            motion_events.extend(self._inside(chunk.motion_events, candidate.start, candidate.end))
            scene_events.extend(self._inside(chunk.scene_events, candidate.start, candidate.end))
            face_events.extend(self._inside(chunk.face_events, candidate.start, candidate.end))
            text_events.extend(self._inside(chunk.text_events, candidate.start, candidate.end))
            transcript_segments.extend(
                segment
                for segment in chunk.transcript_segments
                if self._segments_overlap(segment.start, segment.end, candidate.start, candidate.end)
            )

        candidate.audio_peak = max((event.score for event in audio_events), default=0.0)
        candidate.motion_peak = max((event.score for event in motion_events), default=0.0)
        candidate.face_score = max((event.score for event in face_events), default=0.0)
        candidate.scene_change_count = len(scene_events)
        candidate.has_face = bool(face_events)
        candidate.emotion = self._dominant_emotion(face_events)
        candidate.text_score = self._estimate_text_intensity(text_events, transcript_segments)
        candidate.transcript = " ".join(segment.text.strip() for segment in transcript_segments).strip()
        candidate.transcript_words = [word for segment in transcript_segments for word in segment.words]
        candidate.tags = self._derive_tags(candidate, audio_events, motion_events, scene_events, face_events, transcript_segments)
        subtitle_interest = self._subtitle_interest_from_segments(transcript_segments)
        dialogue_density = self._dialogue_density(candidate.transcript_words, candidate.duration)
        candidate.metadata["subtitle_interest"] = max(float(candidate.metadata.get("subtitle_interest", 0.0) or 0.0), subtitle_interest)
        candidate.metadata["dialogue_density"] = dialogue_density
        candidate.modalities = {
            "audio": candidate.audio_peak,
            "motion": candidate.motion_peak,
            "text": candidate.text_score,
            "face": candidate.face_score,
            "scene": min(1.0, candidate.scene_change_count / 2.0),
            "subtitle": candidate.metadata["subtitle_interest"],
        }
        candidate.metadata["primary_type"] = self._primary_type(candidate)

    def _score_candidate(self, candidate: CandidateMoment) -> float:
        audio_score = float(self.weights.get("audio_peak", 20)) * clamp(candidate.audio_peak, 0.0, 1.0)
        motion_score = float(self.weights.get("motion_peak", 20)) * clamp(candidate.motion_peak, 0.0, 1.0)
        text_score = float(self.weights.get("emotional_phrase", 30)) * clamp(candidate.text_score, 0.0, 1.0)
        exclamation_bonus = float(self.weights.get("exclamation", 15)) if self._has_exclamation(candidate) else 0.0
        scene_score = float(self.weights.get("scene_change", 10)) if candidate.scene_change_count > 0 else 0.0
        face_score = float(self.weights.get("face_emotion", 25)) * clamp(candidate.face_score, 0.0, 1.0)
        subtitle_score = float(self.weights.get("subtitle_hook", 24)) * clamp(
            float(candidate.metadata.get("subtitle_interest", 0.0) or 0.0),
            0.0,
            1.0,
        )
        dialogue_density_score = float(self.weights.get("dialogue_density", 8)) * clamp(
            float(candidate.metadata.get("dialogue_density", 0.0) or 0.0),
            0.0,
            1.0,
        )

        min_clip = float(self.video_config.get("min_clip_duration", 8))
        max_clip = float(self.video_config.get("max_clip_duration", 18))
        target_length = (min_clip + max_clip) / 2.0
        spread = max(2.8, (max_clip - min_clip) / 2.2)
        length_fit = gaussian_score(candidate.duration, target=target_length, spread=spread)
        length_score = float(self.weights.get("optimal_length", 10)) * length_fit
        candidate.length_score = length_score

        total = (
            audio_score
            + motion_score
            + text_score
            + exclamation_bonus
            + scene_score
            + face_score
            + subtitle_score
            + dialogue_density_score
            + length_score
        )
        if {"quiet_loud_payoff", "scene_start"} & set(candidate.source_labels):
            total += 3.0
        if "punchline" in candidate.source_labels:
            total += 4.0
        if "subtitle_hook" in candidate.source_labels:
            total += 6.0
        if not candidate.transcript_words and candidate.duration >= 20:
            total -= 8.0
        return round(min(100.0, total), 2)

    def _select_with_diversity(self, candidates: list[CandidateMoment], video_duration: float) -> list[CandidateMoment]:
        min_count, max_count = self._scaled_range(
            self.video_config.get("target_clips_count", "20-30"),
            video_duration=video_duration,
            unit="count",
        )
        min_total, max_total = self._scaled_range(
            self.video_config.get("target_total_duration", "240-300"),
            video_duration=video_duration,
            unit="seconds",
        )
        overlap_threshold = float(self.video_config.get("overlap_removal_threshold", 2.0))
        diversity_penalty = float(self.weights.get("diversity_penalty", 6))
        repeated_chunk_penalty = float(self.weights.get("repeated_chunk_penalty", 4))

        primary_counter: Counter[str] = Counter()
        chunk_counter: Counter[int] = Counter()
        selected: list[CandidateMoment] = []
        remaining = candidates.copy()

        while remaining:
            best_idx = None
            best_adjusted = -1e9
            for idx, candidate in enumerate(remaining):
                if any(self._overlap_seconds(candidate, picked) > overlap_threshold for picked in selected):
                    continue

                primary = str(candidate.metadata.get("primary_type", self._primary_type(candidate)))
                adjusted = candidate.score
                adjusted -= primary_counter[primary] * diversity_penalty
                adjusted -= max(0, chunk_counter[candidate.chunk_index] - 1) * repeated_chunk_penalty

                if adjusted > best_adjusted:
                    best_adjusted = adjusted
                    best_idx = idx

            if best_idx is None:
                break

            candidate = remaining.pop(best_idx)
            if best_adjusted < 18 and len(selected) >= min_count:
                break

            selected.append(candidate)
            primary = str(candidate.metadata.get("primary_type", self._primary_type(candidate)))
            primary_counter[primary] += 1
            chunk_counter[candidate.chunk_index] += 1

            total_duration = sum(item.duration for item in selected)
            if len(selected) >= max_count or total_duration >= max_total:
                break
            if len(selected) >= min_count and total_duration >= min_total:
                break

        if len(selected) < min_count:
            for candidate in candidates:
                if candidate in selected:
                    continue
                if any(self._overlap_seconds(candidate, picked) > overlap_threshold for picked in selected):
                    continue
                selected.append(candidate)
                if len(selected) >= min_count:
                    break

        return selected

    def _refine_boundaries(
        self,
        candidate: CandidateMoment,
        transcript_segments: list[TranscriptSegment],
        motion_events: list[PeakEvent],
        scene_events: list[PeakEvent],
        text_events: list[PeakEvent],
        video_duration: float,
    ) -> None:
        min_duration = float(self.video_config.get("min_clip_duration", 8))
        max_duration = float(self.video_config.get("max_clip_duration", 18))
        cut_before_word = float(self.cliffhanger.get("cut_before_word", 0.2))
        cut_after_punchline = float(self.cliffhanger.get("cut_after_punchline", 0.3))
        pause_window = float(self.cliffhanger.get("pause_window", 0.6))
        intriguing_words = [word.lower() for word in self.cliffhanger.get("intriguing_words", [])]

        overlapping_segments = [
            segment
            for segment in transcript_segments
            if self._segments_overlap(segment.start, segment.end, candidate.start - 0.5, candidate.end + 1.5)
        ]
        words = [word for segment in overlapping_segments for word in segment.words]
        words.sort(key=lambda item: item.start)

        candidate.start = self._align_start_to_thought(candidate.start, overlapping_segments, words)

        end_reason = "pause"
        current_end = candidate.end
        punchline_segments = [
            segment
            for segment in overlapping_segments
            if segment.punchline_score > 0.35 and segment.end <= candidate.end + 1.4
        ]
        if punchline_segments:
            chosen = max(punchline_segments, key=lambda segment: segment.punchline_score)
            proposed_end = chosen.end + cut_after_punchline
            if proposed_end - candidate.start >= min_duration * 0.92:
                candidate.end = proposed_end
                end_reason = "punchline"
        else:
            exclamation_segments = [
                segment
                for segment in overlapping_segments
                if segment.is_exclamation and segment.end <= candidate.end + 1.0
            ]
            if exclamation_segments:
                chosen = exclamation_segments[-1]
                proposed_end = chosen.end + 0.18
                if proposed_end - candidate.start >= min_duration * 0.92:
                    candidate.end = proposed_end
                    end_reason = "exclamation"
            else:
                next_word_cut = self._cut_before_intriguing_word(candidate.end, words, intriguing_words, cut_before_word)
                if next_word_cut is not None:
                    if next_word_cut - candidate.start >= min_duration * 0.92:
                        candidate.end = next_word_cut
                        end_reason = "intriguing_word"
                else:
                    if "action" in candidate.metadata.get("primary_type", "") or candidate.motion_peak > 0.68:
                        action_peaks = [
                            event
                            for event in motion_events
                            if candidate.end - 2.2 <= event.time <= candidate.end + 0.8
                        ]
                        if action_peaks:
                            chosen = max(action_peaks, key=lambda event: event.score)
                            proposed_end = chosen.time + 0.12
                            if proposed_end - candidate.start >= min_duration * 0.92:
                                candidate.end = proposed_end
                                end_reason = "motion_peak"
                    if end_reason == "pause" and scene_events:
                        nearby_scene = [
                            event for event in scene_events if candidate.end - 1.0 <= event.time <= candidate.end + 0.8
                        ]
                        if nearby_scene:
                            proposed_end = nearby_scene[0].time + 0.08
                            if proposed_end - candidate.start >= min_duration * 0.92:
                                candidate.end = proposed_end
                                end_reason = "scene_cut"
                    if end_reason == "pause":
                        pause_cut = self._nearest_pause_after(candidate.end, words, pause_window)
                        if pause_cut is not None and pause_cut - candidate.start >= min_duration * 0.92:
                            candidate.end = pause_cut

        if candidate.end == current_end:
            end_reason = "full_window"

        candidate.end = clamp(candidate.end, candidate.start + min_duration * 0.8, min(video_duration, candidate.start + max_duration))
        if candidate.end - candidate.start < min_duration:
            candidate.end = min(video_duration, candidate.start + min_duration)
        if candidate.end - candidate.start > max_duration:
            candidate.end = candidate.start + max_duration

        candidate.transcript_words = [
            word for word in words if self._segments_overlap(word.start, word.end, candidate.start, candidate.end)
        ]
        candidate.transcript = self._build_transcript_from_words(candidate.transcript_words, overlapping_segments)
        candidate.end_reason = end_reason
        candidate.thumbnail_time = clamp(candidate.anchor_time, candidate.start, candidate.end)

    def _build_subtitle_candidates(
        self,
        chunks: list[ChunkAnalysis],
        video_duration: float,
        start_index: int = 0,
    ) -> list[CandidateMoment]:
        threshold = float(self.config.get("text", {}).get("subtitle_interest_threshold", 0.52))
        min_duration = float(self.video_config.get("min_clip_duration", 8))
        max_duration = float(self.video_config.get("max_clip_duration", 18))
        target_duration = min(max_duration, max(min_duration, (min_duration + max_duration) / 2.0))
        candidates: list[CandidateMoment] = []
        candidate_index = start_index

        for chunk in chunks:
            segments = chunk.transcript_segments
            if not segments:
                continue

            for index, segment in enumerate(segments):
                interest = self._segment_interest(segment)
                if interest < threshold:
                    continue

                left = index
                right = index
                while segments[right].end - segments[left].start < target_duration:
                    left_gap = (
                        segments[left].start - segments[left - 1].end
                        if left > 0
                        else float("inf")
                    )
                    right_gap = (
                        segments[right + 1].start - segments[right].end
                        if right + 1 < len(segments)
                        else float("inf")
                    )
                    if left_gap <= 2.5 and (left_gap <= right_gap or right + 1 >= len(segments)):
                        left -= 1
                        continue
                    if right_gap <= 2.5:
                        right += 1
                        continue
                    break

                start = max(0.0, segments[left].start - min(4.0, min_duration * 0.18))
                end = min(video_duration, segments[right].end + min(6.0, min_duration * 0.22))
                duration = end - start
                if duration < min_duration:
                    pad = (min_duration - duration) / 2.0
                    start = max(0.0, start - pad)
                    end = min(video_duration, end + pad)
                if end - start > max_duration:
                    anchor_time = (segment.start + segment.end) / 2.0
                    start = max(0.0, anchor_time - max_duration * 0.42)
                    end = min(video_duration, start + max_duration)

                labels = ["subtitle_hook", *segment.tags]
                candidate = CandidateMoment(
                    candidate_id=f"cand_{candidate_index:04d}",
                    start=start,
                    end=end,
                    anchor_time=(segment.start + segment.end) / 2.0,
                    chunk_index=chunk.task.index,
                    source_labels=list(dict.fromkeys(labels)),
                    metadata={"subtitle_interest": interest},
                )
                self._hydrate_candidate(candidate, chunks)
                if candidate.duration >= min_duration * 0.85 and candidate.transcript.strip():
                    candidates.append(candidate)
                    candidate_index += 1

        return candidates

    def _align_start_to_thought(
        self,
        start_time: float,
        segments: list[TranscriptSegment],
        words: list[WordTiming],
    ) -> float:
        if not segments:
            return self._align_start(start_time, words)

        sorted_segments = sorted(segments, key=lambda item: item.start)
        target_index = None
        for idx, segment in enumerate(sorted_segments):
            if segment.start <= start_time <= segment.end:
                target_index = idx
                break
            if start_time < segment.start:
                target_index = idx
                break
        if target_index is None:
            target_index = len(sorted_segments) - 1

        thought_start_index = target_index
        while thought_start_index > 0:
            prev_segment = sorted_segments[thought_start_index - 1]
            current_segment = sorted_segments[thought_start_index]
            gap = current_segment.start - prev_segment.end
            if gap >= 0.85:
                break
            if self._is_sentence_end(prev_segment.text) and not self._looks_like_continuation(current_segment.text):
                break
            thought_start_index -= 1

        natural_start = max(0.0, sorted_segments[thought_start_index].start - 0.06)
        return self._align_start(natural_start, words)

    def _align_start(self, start_time: float, words: list[WordTiming]) -> float:
        for word in words:
            if word.start <= start_time <= word.end:
                return max(0.0, word.start - 0.05)
        for left, right in zip(words, words[1:]):
            if left.end <= start_time <= right.start and right.start - left.end >= 0.18:
                return max(0.0, left.end)
        return max(0.0, start_time)

    @staticmethod
    def _is_sentence_end(text: str) -> bool:
        stripped = text.strip()
        return stripped.endswith((".", "!", "?", "..."))

    @staticmethod
    def _looks_like_continuation(text: str) -> bool:
        lowered = text.strip().lower()
        continuation_prefixes = (
            "where ",
            "when ",
            "and ",
            "but ",
            "or ",
            "because ",
            "so ",
            "then ",
            "if ",
            "while ",
        )
        if lowered.startswith(continuation_prefixes):
            return True
        if lowered and lowered[0].islower():
            return True
        return False

    def _cut_before_intriguing_word(
        self,
        current_end: float,
        words: list[WordTiming],
        intriguing_words: list[str],
        cut_before_word: float,
    ) -> float | None:
        for idx, word in enumerate(words):
            if not (current_end <= word.start <= current_end + 1.4):
                continue
            lowered = re.sub(r"[^\w\-]+", "", word.word.lower(), flags=re.UNICODE)
            window = " ".join(
                re.sub(r"[^\w\-]+", "", words[pos].word.lower(), flags=re.UNICODE)
                for pos in range(idx, min(idx + 3, len(words)))
            ).strip()
            if lowered in intriguing_words or any(window.startswith(phrase) for phrase in intriguing_words):
                return max(0.0, word.start - cut_before_word)
        return None

    def _nearest_pause_after(self, current_end: float, words: list[WordTiming], pause_window: float) -> float | None:
        for left, right in zip(words, words[1:]):
            if left.end < current_end <= right.start and right.start - left.end >= pause_window:
                return left.end + 0.02
        for word in reversed(words):
            if word.end <= current_end:
                return word.end + 0.02
        return None

    @staticmethod
    def _build_transcript_from_words(words: list[WordTiming], segments: list[TranscriptSegment]) -> str:
        if words:
            cleaned = []
            for word in words:
                token = word.word.strip()
                if token:
                    cleaned.append(token)
            text = " ".join(cleaned).replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
            return text.strip()
        return " ".join(segment.text for segment in segments).strip()

    @staticmethod
    def _inside(events: list[PeakEvent], start: float, end: float) -> list[PeakEvent]:
        return [event for event in events if start <= event.time <= end]

    @staticmethod
    def _segments_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> bool:
        return max(a_start, b_start) <= min(a_end, b_end)

    @staticmethod
    def _overlap_seconds(left: CandidateMoment, right: CandidateMoment) -> float:
        return max(0.0, min(left.end, right.end) - max(left.start, right.start))

    def _dominant_emotion(self, face_events: list[PeakEvent]) -> str | None:
        if not face_events:
            return None
        labels = Counter(
            str(event.metadata.get("emotion", "face_present")).lower()
            for event in face_events
            if event.metadata.get("emotion")
        )
        return labels.most_common(1)[0][0] if labels else "face_present"

    def _estimate_text_intensity(
        self,
        text_events: list[PeakEvent],
        transcript_segments: list[TranscriptSegment],
    ) -> float:
        best_event = max((event.score for event in text_events if event.label == "emotional_phrase"), default=0.0)
        question_bonus = max((event.score for event in text_events if event.label == "intriguing_question"), default=0.0)
        punchline_bonus = max((event.score for event in text_events if event.label == "punchline"), default=0.0)
        segment_bonus = self._subtitle_interest_from_segments(transcript_segments)
        return min(1.0, max(best_event, segment_bonus) + 0.25 * question_bonus + 0.35 * punchline_bonus)

    def _subtitle_interest_from_segments(self, transcript_segments: list[TranscriptSegment]) -> float:
        if not transcript_segments:
            return 0.0
        strongest = max((self._segment_interest(segment) for segment in transcript_segments), default=0.0)
        average_top = sum(
            sorted((self._segment_interest(segment) for segment in transcript_segments), reverse=True)[:3]
        ) / min(3, len(transcript_segments))
        return min(1.0, max(strongest, average_top * 0.92))

    @staticmethod
    def _dialogue_density(words: list[WordTiming], duration: float) -> float:
        if not words or duration <= 0:
            return 0.0
        words_per_second = len(words) / max(duration, 1e-6)
        return clamp(words_per_second / 2.2, 0.0, 1.0)

    def _segment_interest(self, segment: TranscriptSegment) -> float:
        score = float(segment.emotional_weight)
        if segment.is_question:
            score += 0.22
        if segment.is_exclamation:
            score += 0.25
        score += min(0.35, float(segment.punchline_score) * 0.5)
        score += min(0.24, 0.06 * len(segment.tags))

        words = re.findall(r"\w+", segment.text, flags=re.UNICODE)
        if len(words) <= 10:
            score += 0.08
        if any(tag in {"intriguing_word", "hook_phrase", "short_hook", "imperative"} for tag in segment.tags):
            score += 0.18
        return min(1.0, score)

    @staticmethod
    def _has_exclamation(candidate: CandidateMoment) -> bool:
        transcript = candidate.transcript.lower()
        return "!" in transcript or "haha" in transcript or "lol" in transcript

    def _derive_tags(
        self,
        candidate: CandidateMoment,
        audio_events: list[PeakEvent],
        motion_events: list[PeakEvent],
        scene_events: list[PeakEvent],
        face_events: list[PeakEvent],
        transcript_segments: list[TranscriptSegment],
    ) -> list[str]:
        tags = set(candidate.source_labels)
        if any(event.label in {"impact_peak", "action_spike"} for event in audio_events + motion_events):
            tags.add("action")
        if scene_events:
            tags.add("scene_change")
        if any(segment.is_question for segment in transcript_segments):
            tags.add("question")
        if any(segment.punchline_score > 0.35 for segment in transcript_segments):
            tags.add("punchline")
        if self._subtitle_interest_from_segments(transcript_segments) >= float(
            self.config.get("text", {}).get("subtitle_interest_threshold", 0.52)
        ):
            tags.add("subtitle_hook")
        if face_events:
            tags.add("reaction")
        if candidate.audio_peak > 0.75 and candidate.motion_peak < 0.45:
            tags.add("audio_drama")
        return sorted(tags)

    def _primary_type(self, candidate: CandidateMoment) -> str:
        subtitle_interest = float(candidate.metadata.get("subtitle_interest", 0.0) or 0.0)
        if subtitle_interest >= 0.58 or candidate.text_score >= max(candidate.audio_peak, candidate.motion_peak):
            return "dialogue"
        if "action" in candidate.tags or candidate.motion_peak >= max(candidate.audio_peak, candidate.text_score):
            return "action"
        if candidate.has_face and candidate.face_score >= 0.55:
            return "reaction"
        if candidate.scene_change_count:
            return "scene_reveal"
        return "hybrid"

    def _scaled_range(self, value: str | int | float, video_duration: float, unit: str) -> tuple[int, int]:
        raw_min, raw_max = self._parse_range(value)
        short_threshold_minutes = float(self.video_config.get("short_video_minutes_threshold", 30))
        minimum_scaled_clips = int(self.video_config.get("minimum_scaled_clips", 6))
        ratio = min(1.0, video_duration / max(short_threshold_minutes * 60.0, 1.0))

        if ratio < 1.0:
            scaled_min = max(1, int(math.ceil(raw_min * ratio)))
            scaled_max = max(scaled_min, int(math.ceil(raw_max * ratio)))
            if unit == "count":
                scaled_min = max(minimum_scaled_clips if video_duration > 12 * 60 else 3, scaled_min)
                scaled_max = max(scaled_min, scaled_max)
            return scaled_min, scaled_max
        return raw_min, raw_max

    @staticmethod
    def _parse_range(value: str | int | float) -> tuple[int, int]:
        if isinstance(value, (int, float)):
            numeric = int(value)
            return numeric, numeric
        text = str(value).strip()
        if "-" not in text:
            numeric = int(float(text))
            return numeric, numeric
        left, right = text.split("-", 1)
        minimum = int(float(left))
        maximum = int(float(right))
        return min(minimum, maximum), max(minimum, maximum)
