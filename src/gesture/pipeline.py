"""Wires camera capture, landmark detection, classification, and temporal
smoothing into the single object `Application`/the UI actually talk to.

Replaces the old `GestureDetector` class. `poll()` is meant to be called
once per UI/loop tick; it applies `gesture.inference_fps` as a throttle so
inference doesn't need to run faster than configured even if the caller
polls more often, and always returns the latest camera frame for preview
even on ticks where inference was skipped.
"""
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from src.config.schema import CameraConfig, GestureConfig
from src.gesture.camera import CameraWorker
from src.gesture.classifier import GestureClassifier
from src.gesture.events import GestureEvent
from src.gesture.landmarks import HandLandmarkerWrapper, draw_landmarks
from src.gesture.smoothing import GestureSmoother


class GesturePipeline:
    def __init__(self, camera_config: CameraConfig, gesture_config: GestureConfig):
        self._gesture_config = gesture_config

        self._camera = CameraWorker(device_index=camera_config.device_index)
        self._landmarker = HandLandmarkerWrapper(
            model_asset_path=gesture_config.model_asset_path,
            min_hand_detection_confidence=gesture_config.min_hand_detection_confidence,
            min_tracking_confidence=gesture_config.min_tracking_confidence,
        )
        self._classifier = GestureClassifier()
        self.smoother = GestureSmoother(
            confirmation_frames=gesture_config.confirmation_frames,
            cooldown_s=gesture_config.cooldown_ms / 1000.0,
        )

        self._min_inference_interval_s = (
            1.0 / gesture_config.inference_fps if gesture_config.inference_fps else 0.0
        )
        self._last_inference_time = 0.0
        self._last_preview_frame: Optional[np.ndarray] = None

    def start(self) -> None:
        self._camera.start()

    def stop(self) -> None:
        self._camera.stop()

    def poll(self) -> Tuple[Optional[GestureEvent], Optional[np.ndarray]]:
        """Returns (event, preview_frame). `event` is None only when no
        camera frame was available at all; once a camera is running it
        always carries at least an idle-state GestureEvent."""
        frame = self._camera.get_latest_frame()
        if frame is None:
            return None, self._last_preview_frame

        frame = cv2.flip(frame, 1)

        now = time.monotonic()
        if self._min_inference_interval_s and (now - self._last_inference_time) < self._min_inference_interval_s:
            # Below the configured inference rate - skip MediaPipe this tick
            # and just hand back the latest preview frame (still useful for
            # a UI camera panel refreshing faster than inference runs).
            preview = self._last_preview_frame if self._last_preview_frame is not None else frame
            return None, preview
        self._last_inference_time = now

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(rgb)

        gesture_name, confidence, hand = None, 0.0, None
        annotated = frame
        if result.hand_landmarks:
            landmarks = result.hand_landmarks[0]
            hand = result.handedness[0] if result.handedness else None
            gesture_name, confidence = self._classifier.classify(landmarks)
            if self._gesture_config.show_landmarks:
                annotated = draw_landmarks(frame, landmarks)

        event = self.smoother.update(gesture_name, confidence, hand)
        self._last_preview_frame = annotated
        return event, annotated
