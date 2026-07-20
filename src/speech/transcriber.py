"""Offline speech-to-text via faster-whisper.

faster-whisper (CTranslate2) over openai-whisper (PyTorch): no torch
dependency, materially lower CPU latency/memory via int8 quantization, and
a multilingual model (never a "*.en" variant) since Amharic support is a
requirement - an English-only model would make that impossible later.

Loaded exactly once and reused for every utterance - mirrors the one thing
the original Vosk-based detector already got right.
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger("speech.transcriber")


@dataclass
class TranscriptResult:
    text: str
    language: Optional[str]
    confidence: float
    latency_ms: float


class WhisperTranscriber:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        pinned_language: Optional[str] = None,
    ):
        from faster_whisper import WhisperModel

        self._pinned_language = pinned_language
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

    def transcribe_pcm16(self, pcm_bytes: bytes, sample_rate: int) -> TranscriptResult:
        if sample_rate != 16000:
            # faster-whisper expects 16kHz mono audio and this pipeline
            # doesn't carry a general-purpose resampler (an extra
            # dependency for a case that shouldn't occur: VAD/capture are
            # both configured for 16kHz by default) - fail loudly instead
            # of silently mis-transcribing.
            raise ValueError(f"WhisperTranscriber requires 16kHz audio, got {sample_rate}Hz")

        start = time.perf_counter()
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        segments, info = self._model.transcribe(audio, language=self._pinned_language, beam_size=1)

        text_parts = []
        confidences = []
        for segment in segments:
            text_parts.append(segment.text)
            # avg_logprob is a log-probability; exp() maps it back to a
            # rough 0-1 scale, discounted by no_speech_prob - not a
            # calibrated confidence, but a defensible ordering signal.
            confidences.append(
                max(0.0, min(1.0, float(np.exp(segment.avg_logprob)))) * (1.0 - segment.no_speech_prob)
            )

        text = " ".join(part.strip() for part in text_parts).strip()
        confidence = float(np.mean(confidences)) if confidences else 0.0
        latency_ms = (time.perf_counter() - start) * 1000

        return TranscriptResult(
            text=text,
            language=getattr(info, "language", None) or self._pinned_language,
            confidence=confidence,
            latency_ms=latency_ms,
        )
