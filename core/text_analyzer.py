from __future__ import annotations

import re
from pathlib import Path

from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

from core.schemas import ChunkTask, PeakEvent, TranscriptSegment, WordTiming

_WHISPER_MODELS: dict[tuple[str, str, str], WhisperModel] = {}


class TextAnalyzer:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.text_config = config.get("text", {})
        self.performance_config = config.get("performance", {})
        self.dictionary = {
            key.lower(): float(value) for key, value in self.text_config.get("emotional_dictionary", {}).items()
        }
        self.intriguing_words = [
            word.lower() for word in self.config.get("cliffhanger", {}).get("intriguing_words", [])
        ]

    def warmup(self) -> None:
        device = "cuda" if bool(self.performance_config.get("use_gpu_whisper", True)) else "cpu"
        if device == "cpu":
            model_name = str(
                self.performance_config.get(
                    "cpu_whisper_model",
                    self.performance_config.get("whisper_model", "tiny"),
                )
            )
        else:
            model_name = str(self.performance_config.get("whisper_model", "medium"))

        self.logger.info("Preparing faster-whisper model %s on %s", model_name, device)
        self._ensure_model_downloaded(model_name)
        self._get_model(force_cpu=(device == "cpu"))
        self.logger.info("Whisper model %s ready on %s", model_name, device)

    def analyze(self, audio_path: str | Path, task: ChunkTask) -> tuple[list[TranscriptSegment], list[PeakEvent], str]:
        try:
            model = self._get_model()
            segments, info = self._transcribe(model, audio_path)
        except Exception as exc:
            if self._is_cuda_runtime_error(exc):
                self.logger.warning("Whisper CUDA runtime unavailable, retrying on CPU: %s", exc)
                model = self._get_model(force_cpu=True)
                segments, info = self._transcribe(model, audio_path)
            else:
                raise

        raw_segments = []
        rendered_text_parts: list[str] = []
        for segment in segments:
            text = (segment.text or "").strip()
            if not text:
                continue
            rendered_text_parts.append(text)
            words: list[WordTiming] = []
            for word in segment.words or []:
                word_text = (word.word or "").strip()
                if not word_text:
                    continue
                words.append(
                    WordTiming(
                        word=word_text,
                        start=task.start + float(word.start),
                        end=task.start + float(word.end),
                        probability=float(getattr(word, "probability", 1.0) or 1.0),
                    )
                )

            segment_start = task.start + float(segment.start)
            segment_end = task.start + float(segment.end)
            emotional_score, tags = self._score_text(text)
            raw_segments.append(
                {
                    "start": segment_start,
                    "end": segment_end,
                    "text": text,
                    "words": words,
                    "emotional_score": emotional_score,
                    "tags": tags,
                    "is_exclamation": "!" in text,
                    "is_question": "?" in text or self._looks_like_question(text),
                }
            )

        transcript_segments: list[TranscriptSegment] = []
        text_events: list[PeakEvent] = []
        for index, item in enumerate(raw_segments):
            next_pause = 0.0
            if index + 1 < len(raw_segments):
                next_pause = max(0.0, raw_segments[index + 1]["start"] - item["end"])
            punchline_score = self._score_punchline(
                text=item["text"],
                tags=item["tags"],
                duration=max(item["end"] - item["start"], 0.001),
                next_pause=next_pause,
            )
            transcript_segment = TranscriptSegment(
                start=item["start"],
                end=item["end"],
                text=item["text"],
                words=item["words"],
                emotional_weight=item["emotional_score"],
                is_question=item["is_question"],
                is_exclamation=item["is_exclamation"],
                punchline_score=punchline_score,
                tags=item["tags"],
            )
            transcript_segments.append(transcript_segment)

            midpoint = (item["start"] + item["end"]) / 2.0
            if item["emotional_score"] > 0:
                text_events.append(
                    PeakEvent(
                        time=midpoint,
                        score=min(1.0, item["emotional_score"]),
                        label="emotional_phrase",
                        source="text",
                        metadata={"text": item["text"], "tags": item["tags"]},
                    )
                )
            if item["is_exclamation"]:
                text_events.append(
                    PeakEvent(
                        time=item["end"],
                        score=1.0,
                        label="exclamation",
                        source="text",
                        metadata={"text": item["text"]},
                    )
                )
            if item["is_question"]:
                text_events.append(
                    PeakEvent(
                        time=item["end"],
                        score=0.75,
                        label="intriguing_question",
                        source="text",
                        metadata={"text": item["text"]},
                    )
                )
            if punchline_score > 0:
                text_events.append(
                    PeakEvent(
                        time=item["end"],
                        score=min(1.0, punchline_score),
                        label="punchline",
                        source="text",
                        metadata={"text": item["text"]},
                    )
                )

        full_text = " ".join(rendered_text_parts).strip()
        return transcript_segments, text_events, full_text

    def _get_model(self, force_cpu: bool = False) -> WhisperModel:
        preferred_device = "cpu" if force_cpu else ("cuda" if bool(self.performance_config.get("use_gpu_whisper", True)) else "cpu")
        if preferred_device == "cpu":
            model_name = str(
                self.performance_config.get(
                    "cpu_whisper_model",
                    self.performance_config.get("whisper_model", "base"),
                )
            )
        else:
            model_name = str(self.performance_config.get("whisper_model", "medium"))
        configured_compute = str(self.performance_config.get("whisper_compute_type", "") or "").strip().lower()
        if preferred_device == "cuda":
            preferred_compute = configured_compute or "float16"
        else:
            cpu_compute = str(
                self.performance_config.get(
                    "cpu_whisper_compute_type",
                    configured_compute or "int8",
                )
            ).strip().lower()
            preferred_compute = cpu_compute if cpu_compute in {"int8", "int8_float32", "float32"} else "int8"

        attempts = [(preferred_device, preferred_compute)]
        if preferred_device != "cpu":
            attempts.append(("cpu", "int8"))

        last_error = None
        for device, compute_type in attempts:
            key = (model_name, device, compute_type)
            if key in _WHISPER_MODELS:
                return _WHISPER_MODELS[key]
            try:
                self.logger.info("Loading faster-whisper model %s on %s (%s)", model_name, device, compute_type)
                _WHISPER_MODELS[key] = WhisperModel(model_name, device=device, compute_type=compute_type)
                return _WHISPER_MODELS[key]
            except Exception as exc:
                last_error = exc
                self.logger.warning(
                    "Failed to load faster-whisper model on %s (%s), trying fallback if available: %s",
                    device,
                    compute_type,
                    exc,
                )

        raise RuntimeError(f"Could not initialize faster-whisper model '{model_name}': {last_error}")

    def _ensure_model_downloaded(self, model_name: str) -> None:
        if Path(model_name).exists():
            return
        repo_id = f"Systran/faster-whisper-{model_name}"
        try:
            self.logger.info("Ensuring Hugging Face model files are available: %s", repo_id)
            snapshot_download(repo_id=repo_id, local_files_only=True)
        except Exception:
            self.logger.info("Downloading Whisper model files from Hugging Face: %s", repo_id)
            snapshot_download(repo_id=repo_id)

    def _transcribe(self, model: WhisperModel, audio_path: str | Path):
        return model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language=self.text_config.get("language"),
            vad_filter=bool(self.text_config.get("vad_filter", True)),
            beam_size=int(self.text_config.get("beam_size", 5)),
            condition_on_previous_text=bool(self.text_config.get("condition_on_previous_text", False)),
        )

    @staticmethod
    def _is_cuda_runtime_error(exc: Exception) -> bool:
        message = str(exc).lower()
        markers = (
            "cublas",
            "cuda",
            "cudnn",
            "cannot be loaded",
            "failed to open library",
        )
        return any(marker in message for marker in markers)

    def _score_text(self, text: str) -> tuple[float, list[str]]:
        lowered = text.lower()
        total = 0.0
        tags: list[str] = []
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        for phrase, weight in self.dictionary.items():
            if phrase in lowered:
                total += weight
                tags.append(phrase)
        if any(word in lowered for word in self.intriguing_words):
            total += 0.4
            tags.append("intriguing_word")
        if re.search(r"\b(?:lol|haha|lmao|rofl)\b", lowered, flags=re.IGNORECASE):
            total += 0.5
            tags.append("laughter")
        if "!" in text:
            total += 0.22
            tags.append("exclamation")
        if "?" in text or self._looks_like_question(text):
            total += 0.2
            tags.append("question")
        if len(words) <= 8 and any(mark in text for mark in ("!", "?", "...")):
            total += 0.18
            tags.append("short_hook")
        if re.search(r"\b(wait|look|run|stop|listen|quick|move|watch|come on)\b", lowered, flags=re.UNICODE):
            total += 0.22
            tags.append("imperative")
        if re.search(
            r"\b(now|seriously|truth|secret|nobody|why|what is that|did you see|no way|i swear)\b",
            lowered,
            flags=re.UNICODE,
        ):
            total += 0.18
            tags.append("hook_phrase")
        return min(total, 1.0), list(dict.fromkeys(tags))

    def _score_punchline(self, text: str, tags: list[str], duration: float, next_pause: float) -> float:
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        max_words = int(self.text_config.get("punchline_max_words", 9))
        pause_required = float(self.text_config.get("punchline_pause_seconds", 0.6))
        short_and_punchy = len(words) <= max_words and duration <= 4.2
        if not short_and_punchy:
            return 0.0
        score = 0.25
        if tags:
            score += 0.35
        if text.endswith(("!", "...", "?!", "?")):
            score += 0.25
        if next_pause >= pause_required:
            score += 0.15
        return min(score, 1.0)

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        lowered = text.lower().strip()
        prefixes = (
            "when",
            "why",
            "how",
            "what",
            "who",
            "where",
            "which",
            "did",
            "does",
            "can",
            "will",
        )
        return lowered.startswith(prefixes)
