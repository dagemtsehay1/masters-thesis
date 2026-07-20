"""Integration test for the voice pipeline's wiring (VAD -> transcriber ->
intent engine), with a fake audio source and a fake transcriber so it runs
without a microphone or the real Whisper model."""
import numpy as np

from src.audio.vad import VoiceActivityDetector
from src.intent.intent_engine import IntentEngine
from src.speech.pipeline import VoicePipeline
from src.speech.transcriber import TranscriptResult


class FakeAudio:
    def __init__(self, chunks):
        self.sample_rate = 16000
        self._chunks = list(chunks)

    def start(self):
        pass

    def stop(self):
        pass

    def read_chunk(self, timeout=None):
        return self._chunks.pop(0) if self._chunks else None


class FakeTranscriber:
    def __init__(self, text):
        self._text = text
        self.calls = 0

    def transcribe_pcm16(self, pcm_bytes, sample_rate):
        self.calls += 1
        return TranscriptResult(text=self._text, language="en", confidence=0.9, latency_ms=1.0)


def _speech_chunk(duration_s=0.1, amplitude=3000):
    n = int(16000 * duration_s)
    return (np.ones((n, 1), dtype=np.int16) * amplitude)


def _silence_chunk(duration_s=0.4):
    n = int(16000 * duration_s)
    return np.zeros((n, 1), dtype=np.int16)


def _make_pipeline(chunks, transcript_text):
    audio = FakeAudio(chunks)
    vad = VoiceActivityDetector(silence_timeout_s=0.2, backend="energy", energy_threshold=500.0)
    transcriber = FakeTranscriber(transcript_text)
    intent = IntentEngine(language="en", confidence_threshold=0.4)
    return VoicePipeline(audio, vad, transcriber, intent), transcriber


def test_pipeline_yields_no_event_on_silence_only():
    pipeline, transcriber = _make_pipeline([_silence_chunk(), _silence_chunk()], "go forward")
    for _ in range(2):
        event, _waveform = pipeline.poll()
        assert event is None
    assert transcriber.calls == 0  # transcriber never invoked on pure silence


def test_pipeline_transcribes_and_resolves_a_command_after_speech_then_silence():
    chunks = [_speech_chunk(), _speech_chunk(), _silence_chunk()]
    pipeline, transcriber = _make_pipeline(chunks, "go forward")

    events = []
    for _ in range(len(chunks)):
        event, _waveform = pipeline.poll()
        if event is not None:
            events.append(event)

    assert transcriber.calls == 1
    assert len(events) == 1
    assert events[0].command == "go"  # "go forward" -> canonical move_forward -> legacy "go"


def test_pipeline_returns_waveform_samples_for_visualization():
    pipeline, _ = _make_pipeline([_speech_chunk()], "go forward")
    _event, waveform = pipeline.poll()
    assert waveform is not None
    assert waveform.dtype == np.float32
