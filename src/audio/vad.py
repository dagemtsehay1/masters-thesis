"""Voice activity detection - the gate that decides when Whisper actually
needs to run.

Accumulates raw PCM until a complete utterance is ready: speech detected,
then either `silence_timeout_s` of trailing silence or `max_recording_s`
total, whichever comes first. Silent audio never reaches the transcriber.

Time is measured in *audio* time (from the number of samples consumed), not
wall-clock time. This matters: if whatever is feeding the VAD stalls or
runs faster than real time, an utterance's boundaries should still be
defined by the audio's own duration, not by how quickly frames happened to
be delivered.

`webrtcvad` is the default backend (tiny, pure-C, no model download); a
simple RMS-energy threshold is available as a fallback in case webrtcvad
proves unreliable on a given microphone - this is an explicit assumption
since no specific hardware was available to validate against.
"""
import logging

import numpy as np

logger = logging.getLogger("audio.vad")


class VoiceActivityDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        silence_timeout_s: float = 0.6,
        max_recording_s: float = 8.0,
        aggressiveness: int = 2,
        backend: str = "webrtcvad",
        energy_threshold: float = 500.0,
    ):
        self.sample_rate = sample_rate
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.frame_bytes = self.frame_samples * 2  # int16 = 2 bytes/sample
        self._frame_duration_s = frame_ms / 1000.0
        self.silence_timeout_s = silence_timeout_s
        self.max_recording_s = max_recording_s
        self._energy_threshold = energy_threshold

        self._vad = None
        if backend == "webrtcvad":
            try:
                import webrtcvad

                self._vad = webrtcvad.Vad(aggressiveness)
            except Exception:
                logger.warning("webrtcvad unavailable, falling back to an energy threshold")

        self._buffer = bytearray()
        self._utterance = bytearray()
        self._speech_started = False
        self._trailing_silence_s = 0.0
        self._recording_elapsed_s = 0.0

    def _is_speech_frame(self, frame: bytes) -> bool:
        if self._vad is not None:
            try:
                return self._vad.is_speech(frame, self.sample_rate)
            except Exception:
                logger.debug("webrtcvad.is_speech failed, falling back to energy for this frame")

        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(samples**2)))
        return rms > self._energy_threshold

    def feed(self, pcm_bytes: bytes) -> bytes | None:
        """Feed raw int16 PCM bytes. Returns a complete utterance's bytes
        once one is ready (speech followed by enough silence, or the max
        recording length was hit), otherwise None."""
        self._buffer.extend(pcm_bytes)

        utterance_ready = None
        while len(self._buffer) >= self.frame_bytes:
            frame = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]

            is_speech = self._is_speech_frame(frame)

            if is_speech and not self._speech_started:
                self._speech_started = True
                self._utterance = bytearray()
                self._trailing_silence_s = 0.0
                self._recording_elapsed_s = 0.0

            if self._speech_started:
                self._utterance.extend(frame)
                self._recording_elapsed_s += self._frame_duration_s
                self._trailing_silence_s = 0.0 if is_speech else self._trailing_silence_s + self._frame_duration_s

                if (
                    self._trailing_silence_s >= self.silence_timeout_s
                    or self._recording_elapsed_s >= self.max_recording_s
                ):
                    utterance_ready = bytes(self._utterance)
                    self._speech_started = False
                    self._utterance = bytearray()

        return utterance_ready
