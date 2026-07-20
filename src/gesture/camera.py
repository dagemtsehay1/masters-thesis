"""Decoupled camera capture.

Reads frames on its own thread so a slow gesture inference call never
blocks (or is blocked by) frame acquisition. Only the single newest frame
is ever kept - if inference hasn't consumed the previous one yet, it's
dropped rather than queued, which is what keeps the pipeline from ever
processing a backlog of stale frames.
"""
import logging
import queue
import threading
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("gesture.camera")


class CameraWorker:
    def __init__(self, device_index: int = 0):
        self._device_index = device_index
        self._cap = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=1)

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open camera device {self._device_index}")

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _run(self) -> None:
        while self._running and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret:
                continue
            self._put_latest(frame)

    def _put_latest(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                self._queue.get_nowait()  # drop the stale frame
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass

    def get_latest_frame(self) -> Optional[np.ndarray]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
