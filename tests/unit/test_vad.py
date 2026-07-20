import numpy as np

from src.audio.vad import VoiceActivityDetector


def _pcm(amplitude, duration_s, sample_rate=16000):
    n = int(sample_rate * duration_s)
    return (np.ones(n, dtype=np.int16) * amplitude).tobytes()


def _silence(duration_s, sample_rate=16000):
    return _pcm(0, duration_s, sample_rate)


def _speech(duration_s, sample_rate=16000):
    return _pcm(3000, duration_s, sample_rate)


def _make_vad(**overrides):
    # Force the energy backend so this test is deterministic and doesn't
    # depend on webrtcvad being installed.
    params = dict(
        sample_rate=16000,
        frame_ms=20,
        silence_timeout_s=0.3,
        max_recording_s=5.0,
        backend="energy",
        energy_threshold=500.0,
    )
    params.update(overrides)
    return VoiceActivityDetector(**params)


def test_pure_silence_never_produces_an_utterance():
    vad = _make_vad()
    for _ in range(20):
        assert vad.feed(_silence(0.1)) is None


def test_speech_then_silence_produces_an_utterance():
    vad = _make_vad(silence_timeout_s=0.2)

    assert vad.feed(_speech(0.3)) is None  # still speaking, not done yet

    # Trailing silence longer than the timeout should close the utterance.
    utterance = vad.feed(_silence(0.3))
    assert utterance is not None
    assert len(utterance) > 0


def test_max_recording_length_forces_an_utterance_even_without_silence():
    vad = _make_vad(silence_timeout_s=10.0, max_recording_s=0.4)
    result = None
    for _ in range(10):
        result = vad.feed(_speech(0.1))
        if result is not None:
            break
    assert result is not None
