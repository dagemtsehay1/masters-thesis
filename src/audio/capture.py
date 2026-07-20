"""Microphone capture, decoupled from anything that consumes it.

Mirrors `src/gesture/camera.py`'s pattern: a background callback feeds a
small bounded queue (drop-oldest on overflow) so a slow consumer never
causes unbounded memory growth or backpressure into the audio driver.
"""
import logging
import queue
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger("audio.capture")


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        device_index: Optional[int] = None,
        channels: int = 1,
        blocksize: int = 512,
        max_queued_chunks: int = 50,
    ):
        self.sample_rate = sample_rate
        self._device_index = device_index
        self._channels = channels
        self._blocksize = blocksize
        self._stream = None
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=max_queued_chunks)

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.debug("sounddevice status: %s", status)
        chunk = indata.copy()
        try:
            self._queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                pass

    def start(self) -> None:
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self._channels,
            blocksize=self._blocksize,
            dtype="int16",
            device=self._device_index,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read_chunk(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
