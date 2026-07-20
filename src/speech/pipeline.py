"""Wires audio capture, VAD gating, transcription, and intent resolution
into the single object `Application`/the UI actually talk to - mirrors
`src/gesture/pipeline.py::GesturePipeline`'s `poll()` shape so both
entrypoints can treat voice and gesture identically.
"""
import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("speech.pipeline")


class VoicePipeline:
    def __init__(self, audio, vad, transcriber, intent_engine):
        self._audio = audio
        self._vad = vad
        self._transcriber = transcriber
        self._intent_engine = intent_engine

    def start(self) -> None:
        self._audio.start()

    def stop(self) -> None:
        self._audio.stop()

    def poll(self, chunk_timeout_s: float = 0.05) -> Tuple[Optional[object], Optional[np.ndarray]]:
        """Returns (VoiceEvent | None, waveform_samples | None). Blocks for
        at most `chunk_timeout_s` waiting for the next audio chunk - the
        transcription call itself (only reached once an utterance is
        complete) is not bounded by that timeout and may take noticeably
        longer, which is why this belongs on its own thread in the GUI."""
        chunk = self._audio.read_chunk(timeout=chunk_timeout_s)
        if chunk is None:
            return None, None

        waveform_samples = (chunk.astype(np.float32) / 32768.0).flatten()

        utterance = self._vad.feed(chunk.tobytes())
        if utterance is None:
            return None, waveform_samples

        try:
            result = self._transcriber.transcribe_pcm16(utterance, self._audio.sample_rate)
        except Exception:
            logger.exception("Transcription failed")
            return None, waveform_samples

        if result.text:
            logger.info("Transcribed '%s' in %.0fms (confidence=%.2f)", result.text, result.latency_ms, result.confidence)

        event = self._intent_engine.resolve(result.text, result.confidence, language=result.language)
        return event, waveform_samples
