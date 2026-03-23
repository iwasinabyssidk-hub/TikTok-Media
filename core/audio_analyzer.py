from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
from scipy.signal import find_peaks

from core.schemas import ChunkTask, PeakEvent
from utils.cache_manager import CacheManager
from utils.ffmpeg_utils import clamp, extract_audio


class AudioAnalyzer:


    def __init__(self, config: dict, cache: CacheManager, logger) -> None:
        self.config = config
        self.cache = cache
        self.logger = logger
        self.sample_rate = int(config["performance"]["audio_sample_rate"])
        self.audio_config = config.get("audio", {})

    def get_or_extract_audio(self, video_path: str, task: ChunkTask) -> Path:
        key = self.cache.build_key(
            "audio_chunk",
            {
                "video_path": video_path,
                "start": round(task.start, 3),
                "end": round(task.end, 3),
                "sample_rate": self.sample_rate,
            },
        )
        audio_path = self.cache.resolve_path("audio", f"{key}.wav")
        if audio_path.exists():
            return audio_path
        return extract_audio(
            video_path=video_path,
            audio_path=audio_path,
            start=task.start,
            end=task.end,
            sample_rate=self.sample_rate,
        )

    def analyze(self, audio_path: str | Path, task: ChunkTask) -> tuple[list[PeakEvent], dict[str, float]]:
        y, sr = librosa.load(str(audio_path), sr=self.sample_rate, mono=True)
        if y.size == 0:
            return [], {"max_rms": 0.0, "mean_rms": 0.0}

        hop_length = 512
        frame_length = 2048

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop_length)[0]
        flatness = librosa.feature.spectral_flatness(y=y, hop_length=hop_length)[0]


        stft = np.abs(librosa.stft(y=y, n_fft=2048, hop_length=hop_length))
        flux = np.sqrt(np.sum(np.diff(stft, axis=1, prepend=stft[:, :1]) ** 2, axis=0))
        flux = flux[: rms.shape[0]]

        rms_norm = self._normalize(rms)
        onset_norm = self._normalize(onset)
        centroid_delta = self._normalize(np.abs(np.diff(centroid, prepend=centroid[:1])))
        bandwidth_delta = self._normalize(np.abs(np.diff(bandwidth, prepend=bandwidth[:1])))
        flux_norm = self._normalize(flux)
        noise_penalty = 1.0 - np.clip(self._normalize(flatness), 0.0, 0.65)

        combined = (
            0.38 * rms_norm
            + 0.24 * onset_norm
            + 0.18 * flux_norm
            + 0.12 * centroid_delta
            + 0.08 * bandwidth_delta
        ) * noise_penalty
        combined = np.clip(combined, 0.0, 1.0)

        times = librosa.frames_to_time(np.arange(combined.shape[0]), sr=sr, hop_length=hop_length)
        prominence = float(self.audio_config.get("peak_prominence", 0.18))
        min_distance = max(
            1,
            int(float(self.audio_config.get("min_peak_distance_seconds", 1.1)) * sr / hop_length),
        )
        lower_bound = np.percentile(combined, float(self.audio_config.get("ignore_below_percentile", 55)))

        peaks, properties = find_peaks(combined, prominence=prominence, distance=min_distance, height=lower_bound)
        events: list[PeakEvent] = []

        quiet_window = int(float(self.audio_config.get("quiet_window_seconds", 2.5)) * sr / hop_length)
        loud_window = int(float(self.audio_config.get("loud_window_seconds", 1.5)) * sr / hop_length)

        for peak_index in peaks:
            peak_time = task.start + float(times[peak_index])
            score = float(combined[peak_index])
            quiet_slice = rms_norm[max(0, peak_index - quiet_window) : peak_index]
            loud_slice = rms_norm[peak_index : min(rms_norm.shape[0], peak_index + loud_window)]
            quiet_before = float(np.mean(quiet_slice)) if quiet_slice.size else 0.0
            loud_after = float(np.max(loud_slice)) if loud_slice.size else score
            music_shift = float(max(flux_norm[peak_index], centroid_delta[peak_index], bandwidth_delta[peak_index]))

            label = "audio_peak"
            if quiet_before < 0.32 and score > 0.7:
                label = "quiet_loud_payoff"
            if music_shift > 0.7 and score > 0.48:
                label = "music_shift"
            if onset_norm[peak_index] > 0.78 and rms_norm[peak_index] > 0.72:
                label = "impact_peak"

            events.append(
                PeakEvent(
                    time=peak_time,
                    score=score,
                    label=label,
                    source="audio",
                    metadata={
                        "rms": float(rms_norm[peak_index]),
                        "onset": float(onset_norm[peak_index]),
                        "music_shift": music_shift,
                        "quiet_before": quiet_before,
                        "loud_after": loud_after,
                        "prominence": float(properties["prominences"][list(peaks).index(peak_index)]),
                    },
                )
            )

        stats = {
            "max_rms": float(np.max(rms_norm)) if rms_norm.size else 0.0,
            "mean_rms": float(np.mean(rms_norm)) if rms_norm.size else 0.0,
            "peaks_found": float(len(events)),
        }
        return events, stats

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        low = float(np.percentile(values, 5))
        high = float(np.percentile(values, 95))
        if high - low < 1e-8:
            return np.zeros_like(values, dtype=np.float32)
        normalized = (values - low) / (high - low)
        return np.clip(normalized.astype(np.float32), 0.0, 1.0)
