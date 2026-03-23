from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from core.schemas import ChunkTask, PeakEvent

try:
    from deepface import DeepFace
except Exception:
    DeepFace = None


class FaceAnalyzer:


    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.face_config = config.get("faces", {})
        self.performance_config = config.get("performance", {})
        self.enabled = bool(self.face_config.get("enabled", True))
        if not bool(self.performance_config.get("use_gpu_whisper", True)) and bool(
            self.performance_config.get("skip_face_on_cpu", True)
        ):
            self.enabled = False
        self.detector_backend = str(self.face_config.get("detector_backend", "opencv"))
        self.emotion_weights = {
            key.lower(): float(value) for key, value in self.face_config.get("dominant_emotions", {}).items()
        }
        self.cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def analyze(self, video_path: str, task: ChunkTask) -> tuple[list[PeakEvent], dict[str, float]]:
        if not self.enabled:
            return [], {"face_hits": 0.0}

        capture = cv2.VideoCapture(video_path)
        if not capture.isOpened():
            self.logger.warning("Could not open video for face analysis: %s", video_path)
            return [], {"face_hits": 0.0}

        if bool(self.performance_config.get("use_gpu_whisper", True)):
            sample_every = float(self.performance_config.get("face_sample_seconds", 2.0))
        else:
            sample_every = float(
                self.performance_config.get(
                    "cpu_face_sample_seconds",
                    self.performance_config.get("face_sample_seconds", 2.0),
                )
            )
        current_time = task.start
        events: list[PeakEvent] = []
        max_face_score = 0.0

        while current_time < task.end:
            capture.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000.0)
            ok, frame = capture.read()
            if not ok:
                current_time += sample_every
                continue

            analysis = self._analyze_frame(frame)
            if analysis is not None:
                emotion = analysis["emotion"]
                emotion_score = float(analysis["score"])
                max_face_score = max(max_face_score, emotion_score)
                events.append(
                    PeakEvent(
                        time=current_time,
                        score=emotion_score,
                        label="face_emotion",
                        source="face",
                        metadata={
                            "emotion": emotion,
                            "face_count": analysis["face_count"],
                        },
                    )
                )
            current_time += sample_every

        capture.release()
        return events, {"face_hits": float(len(events)), "max_face_score": max_face_score}

    def _analyze_frame(self, frame: np.ndarray) -> dict[str, Any] | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
        if len(faces) == 0:
            return None

        if DeepFace is not None:
            try:
                result = DeepFace.analyze(
                    img_path=frame,
                    actions=["emotion"],
                    detector_backend=self.detector_backend,
                    enforce_detection=False,
                    silent=True,
                )
                payload = result[0] if isinstance(result, list) else result
                dominant = str(payload.get("dominant_emotion", "neutral")).lower()
                score = float(self.emotion_weights.get(dominant, 0.35))
                return {
                    "emotion": dominant,
                    "score": score,
                    "face_count": len(faces),
                }
            except Exception as exc:
                self.logger.debug("DeepFace failed, falling back to face-presence only: %s", exc)


        area_scores = []
        frame_area = frame.shape[0] * frame.shape[1]
        for x, y, w, h in faces:
            area_scores.append((w * h) / max(frame_area, 1))
        face_presence = float(min(1.0, max(area_scores) * 12.0))
        return {
            "emotion": "face_present",
            "score": max(face_presence, 0.35),
            "face_count": len(faces),
        }
