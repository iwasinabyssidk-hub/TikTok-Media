from __future__ import annotations

import cv2
import numpy as np
from scipy.signal import find_peaks

from core.schemas import ChunkTask, PeakEvent


class SceneDetector:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.scene_config = config.get("scenes", {})
        self.performance_config = config.get("performance", {})

    def analyze(self, video_path: str, task: ChunkTask) -> tuple[list[PeakEvent], dict[str, float]]:
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            self.logger.warning("Could not open video for scene analysis: %s", video_path)
            return [], {"max_histogram_diff": 0.0}

        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        use_gpu_profile = bool(self.performance_config.get("use_gpu_whisper", True))
        fast_cpu_visual_mode = bool(self.performance_config.get("fast_cpu_visual_mode", True))
        if use_gpu_profile:
            step = max(1, int(self.performance_config.get("scene_frame_step", 5)))
        else:
            step = max(
                1,
                int(
                    self.performance_config.get(
                        "cpu_scene_frame_step",
                        self.performance_config.get("scene_frame_step", 5),
                    )
                ),
            )
        threshold = float(self.scene_config.get("cut_threshold", 0.52))
        min_gap_seconds = float(self.scene_config.get("min_scene_gap_seconds", 1.2))
        if use_gpu_profile:
            resize_width = int(self.scene_config.get("resize_width", 320))
            resize_height = int(self.scene_config.get("resize_height", 180))
        else:
            resize_width = int(self.scene_config.get("cpu_resize_width", self.scene_config.get("resize_width", 320)))
            resize_height = int(self.scene_config.get("cpu_resize_height", self.scene_config.get("resize_height", 180)))
        use_fast_diff = (not use_gpu_profile) and fast_cpu_visual_mode
        bins = int(self.scene_config.get("histogram_bins", 32))
        if fps <= float(self.performance_config.get("proxy_low_fps_threshold", 4.5)):
            step = 1

        start_frame = int(task.start * fps)
        end_frame = int(task.end * fps)
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        previous_hist = None
        previous_gray = None
        previous_mean = None
        hist_diffs: list[float] = []
        hist_times: list[float] = []
        frame_index = start_frame

        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break

            small = cv2.resize(frame, (resize_width, resize_height), interpolation=cv2.INTER_AREA)
            current_time = frame_index / fps
            if use_fast_diff:
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                mean_color = np.mean(small, axis=(0, 1))
                if previous_gray is not None and previous_mean is not None:
                    frame_delta = float(np.mean(cv2.absdiff(previous_gray, gray))) / 255.0
                    color_delta = float(np.mean(np.abs(mean_color - previous_mean))) / 255.0
                    hist_diffs.append(0.8 * frame_delta + 0.2 * color_delta)
                    hist_times.append(current_time)
                previous_gray = gray
                previous_mean = mean_color
            else:
                hist = cv2.calcHist([small], [0, 1, 2], None, [bins, bins, bins], [0, 256, 0, 256, 0, 256])
                hist = cv2.normalize(hist, hist).flatten()
                if previous_hist is not None:
                    correlation = cv2.compareHist(previous_hist.astype(np.float32), hist.astype(np.float32), cv2.HISTCMP_CORREL)
                    difference = float(1.0 - max(min(correlation, 1.0), -1.0))
                    hist_diffs.append(difference)
                    hist_times.append(current_time)
                previous_hist = hist

            skipped = self._skip_frames(capture, step - 1, frame_index, end_frame)
            frame_index += 1 + skipped

        capture.release()

        if not hist_times:
            return [], {"max_histogram_diff": 0.0}

        raw_diffs = np.asarray(hist_diffs, dtype=np.float32)
        normalized_diffs = self._normalize(raw_diffs)
        min_distance = max(1, int(min_gap_seconds / max(step / fps, 1e-4)))
        peak_indices, _ = find_peaks(normalized_diffs, prominence=max(0.18, threshold * 0.45), distance=min_distance)

        events: list[PeakEvent] = []
        last_cut = -1e9
        candidate_indices = peak_indices.tolist() if len(peak_indices) else list(range(len(hist_times)))
        for peak_index in candidate_indices:
            current_time = float(hist_times[peak_index])
            diff_value = float(normalized_diffs[peak_index])
            raw_value = float(raw_diffs[peak_index])
            if diff_value < threshold:
                continue
            if current_time - last_cut < min_gap_seconds:
                continue
            last_cut = current_time
            events.append(
                PeakEvent(
                    time=float(current_time),
                    score=float(min(diff_value, 1.0)),
                    label="scene_cut",
                    source="scene",
                    metadata={"histogram_diff": raw_value},
                )
            )

            reveal_time = min(task.end, current_time + 0.8)
            events.append(
                PeakEvent(
                    time=float(reveal_time),
                    score=float(min(diff_value * 0.85, 1.0)),
                    label="scene_start",
                    source="scene",
                    metadata={"histogram_diff": raw_value},
                )
            )

        stats = {
            "max_histogram_diff": float(np.max(raw_diffs) if raw_diffs.size else 0.0),
            "scene_events": float(len(events)),
            "algorithm": "frame_diff" if use_fast_diff else "histogram",
        }
        return events, stats

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        low = float(np.percentile(values, 10))
        high = float(np.percentile(values, 95))
        if high - low < 1e-8:
            return np.zeros_like(values)
        return np.clip((values - low) / (high - low), 0.0, 1.0)

    @staticmethod
    def _skip_frames(capture: cv2.VideoCapture, skip_count: int, frame_index: int, end_frame: int) -> int:
        if skip_count <= 0:
            return 0
        skipped = 0
        while skipped < skip_count and frame_index + skipped + 1 <= end_frame:
            if not capture.grab():
                break
            skipped += 1
        return skipped
