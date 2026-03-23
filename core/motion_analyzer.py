from __future__ import annotations

import cv2
import numpy as np
from scipy.signal import find_peaks

from core.schemas import ChunkTask, PeakEvent


class MotionAnalyzer:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.motion_config = config.get("motion", {})
        self.performance_config = config.get("performance", {})

    def analyze(self, video_path: str, task: ChunkTask) -> tuple[list[PeakEvent], dict[str, float]]:
        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            self.logger.warning("Could not open video for motion analysis: %s", video_path)
            return [], {"max_motion": 0.0}

        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        use_gpu_profile = bool(self.performance_config.get("use_gpu_whisper", True))
        fast_cpu_visual_mode = bool(self.performance_config.get("fast_cpu_visual_mode", True))
        if use_gpu_profile:
            frame_step = max(1, int(self.performance_config.get("motion_frame_step", 5)))
        else:
            frame_step = max(
                1,
                int(
                    self.performance_config.get(
                        "cpu_motion_frame_step",
                        self.performance_config.get("motion_frame_step", 5),
                    )
                ),
            )
        if use_gpu_profile:
            resize_width = int(self.motion_config.get("resize_width", 320))
        else:
            resize_width = int(self.motion_config.get("cpu_resize_width", self.motion_config.get("resize_width", 320)))
        use_fast_diff = (not use_gpu_profile) and fast_cpu_visual_mode
        if fps <= float(self.performance_config.get("proxy_low_fps_threshold", 4.5)):
            frame_step = 1

        start_frame = int(task.start * fps)
        end_frame = int(task.end * fps)
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        prev_gray = None
        prev_brightness = None
        sample_times: list[float] = []
        motion_values: list[float] = []
        light_changes: list[float] = []
        frame_index = start_frame
        while frame_index <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            processed = self._prepare_frame(frame, resize_width=resize_width)
            gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)
            brightness = float(np.mean(gray))

            if prev_gray is not None:
                if use_fast_diff:
                    motion_values.append(self._frame_diff_motion(prev_gray, gray))
                else:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev=prev_gray,
                        next=gray,
                        flow=None,
                        pyr_scale=0.5,
                        levels=2,
                        winsize=11,
                        iterations=2,
                        poly_n=5,
                        poly_sigma=1.1,
                        flags=0,
                    )
                    magnitude = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                    motion_values.append(float(np.mean(magnitude)))
                light_changes.append(abs(brightness - float(prev_brightness)))
                sample_times.append(frame_index / fps)

            prev_gray = gray
            prev_brightness = brightness
            skipped = self._skip_frames(capture, frame_step - 1, frame_index, end_frame)
            frame_index += 1 + skipped

        capture.release()

        if not sample_times:
            return [], {"max_motion": 0.0}

        motion_norm = self._normalize(np.asarray(motion_values, dtype=np.float32))
        light_norm = self._normalize(np.asarray(light_changes, dtype=np.float32))
        combined = np.clip(0.82 * motion_norm + 0.18 * light_norm, 0.0, 1.0)

        min_distance = max(
            1,
            int(float(self.motion_config.get("min_peak_distance_seconds", 1.0)) / max(frame_step / fps, 1e-4)),
        )
        motion_peaks, _ = find_peaks(
            combined,
            prominence=float(self.motion_config.get("flow_peak_prominence", 0.18)),
            distance=min_distance,
        )
        flash_peaks, _ = find_peaks(
            light_norm,
            prominence=float(self.motion_config.get("light_change_prominence", 0.2)),
            distance=min_distance,
        )

        events: list[PeakEvent] = []
        for peak_index in motion_peaks:
            label = "motion_peak"
            if motion_norm[peak_index] > 0.78:
                label = "action_spike"
            events.append(
                PeakEvent(
                    time=float(sample_times[peak_index]),
                    score=float(combined[peak_index]),
                    label=label,
                    source="motion",
                    metadata={
                        "motion": float(motion_norm[peak_index]),
                        "light_change": float(light_norm[peak_index]),
                    },
                )
            )

        for peak_index in flash_peaks:
            events.append(
                PeakEvent(
                    time=float(sample_times[peak_index]),
                    score=float(light_norm[peak_index]),
                    label="light_flash",
                    source="motion",
                    metadata={
                        "motion": float(motion_norm[peak_index]),
                        "light_change": float(light_norm[peak_index]),
                    },
                )
            )

        stats = {
            "max_motion": float(np.max(motion_norm)),
            "mean_motion": float(np.mean(motion_norm)),
            "max_light_change": float(np.max(light_norm)),
            "algorithm": "frame_diff" if use_fast_diff else "farneback",
        }
        return events, stats

    @staticmethod
    def _prepare_frame(frame: np.ndarray, resize_width: int) -> np.ndarray:
        height, width = frame.shape[:2]
        scale = resize_width / max(width, 1)
        new_size = (resize_width, max(1, int(height * scale)))
        return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        low = float(np.percentile(values, 5))
        high = float(np.percentile(values, 95))
        if high - low < 1e-8:
            return np.zeros_like(values)
        return np.clip((values - low) / (high - low), 0.0, 1.0)

    @staticmethod
    def _frame_diff_motion(prev_gray: np.ndarray, gray: np.ndarray) -> float:
        diff = cv2.absdiff(prev_gray, gray)
        diff_mean = float(np.mean(diff)) / 255.0
        active_ratio = float(np.count_nonzero(diff > 18)) / float(diff.size or 1)
        return 0.7 * diff_mean + 0.3 * min(active_ratio * 4.0, 1.0)

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
