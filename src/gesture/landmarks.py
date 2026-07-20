"""Thin wrapper around MediaPipe's HandLandmarker.

Owns exactly one `HandLandmarker` instance (loaded once, per the "load each
model once" performance requirement) and hides the monotonic-timestamp
bookkeeping `detect_for_video` requires. Classification and drawing are
deliberately not this module's job - see classifier.py and draw_landmarks().
"""
import time
from dataclasses import dataclass
from typing import List, Optional

import cv2
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import mediapipe as mp


@dataclass
class HandDetectionResult:
    hand_landmarks: List[list]
    handedness: List[Optional[str]]


class HandLandmarkerWrapper:
    def __init__(
        self,
        model_asset_path: str,
        min_hand_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.6,
        num_hands: int = 1,
    ):
        self._last_timestamp_ms = 0

        base_options = python.BaseOptions(model_asset_path=model_asset_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_hand_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    def detect(self, rgb_frame: np.ndarray) -> HandDetectionResult:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        timestamp_ms = int(time.time() * 1000)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms

        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)

        handedness = []
        for hand_categories in result.handedness or []:
            handedness.append(hand_categories[0].category_name if hand_categories else None)

        return HandDetectionResult(hand_landmarks=result.hand_landmarks or [], handedness=handedness)


def draw_landmarks(frame_bgr: np.ndarray, landmarks) -> np.ndarray:
    """Debug overlay - only called when gesture.show_landmarks is enabled."""
    annotated = frame_bgr.copy()
    h, w, _ = annotated.shape
    for lm in landmarks:
        cx, cy = int(lm.x * w), int(lm.y * h)
        cv2.circle(annotated, (cx, cy), 5, (0, 255, 0), -1)
    return annotated
