import time
from datetime import datetime, timedelta, timezone

import pytest

from src.config.schema import FusionConfig
from src.fusion.engine import FusionEngine
from src.gesture.events import GestureEvent
from src.voice.events import VoiceEvent


def _voice(command, confidence=0.9, age_s=0.0):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    return VoiceEvent(command=command, confidence=confidence, timestamp=ts)


def _gesture(gesture, confidence=0.9, age_s=0.0, state="confirmed"):
    ts = datetime.now(timezone.utc) - timedelta(seconds=age_s)
    return GestureEvent(gesture=gesture, confidence=confidence, state=state, timestamp=ts)


def test_stop_overrides_the_configured_mode_from_either_modality():
    engine = FusionEngine(FusionConfig(mode="gesture_priority"))
    decision = engine.resolve(voice_event=_voice("stop"), gesture_event=None)
    assert decision is not None
    assert decision.command.action == "stop"
    assert decision.command.source == "voice"


def test_stop_from_both_modalities_is_tagged_combined():
    engine = FusionEngine(FusionConfig(mode="voice_priority"))
    decision = engine.resolve(voice_event=_voice("stop"), gesture_event=_gesture("stop"))
    assert decision.command.source == "combined"


def test_voice_priority_mode_prefers_voice():
    engine = FusionEngine(FusionConfig(mode="voice_priority"))
    decision = engine.resolve(voice_event=_voice("go"), gesture_event=_gesture("left"))
    assert decision.command.source == "voice"
    assert decision.command.action == "move"


def test_stale_gesture_event_is_ignored():
    engine = FusionEngine(FusionConfig(mode="gesture_priority", stale_event_timeout_ms=200))
    decision = engine.resolve(voice_event=None, gesture_event=_gesture("go", age_s=5.0))
    assert decision is None


def test_low_confidence_voice_event_is_rejected():
    config = FusionConfig(mode="voice_priority")
    config.minimum_confidence.voice = 0.8
    engine = FusionEngine(config)
    decision = engine.resolve(voice_event=_voice("go", confidence=0.3), gesture_event=None)
    assert decision is None


def test_duplicate_command_within_cooldown_is_suppressed():
    # stale_event_timeout_ms is raised well above the 2s offset used below so
    # this test isolates duplicate-cooldown behavior from stale-event
    # filtering (the two would otherwise sit on the same boundary and make
    # the third assertion flaky).
    engine = FusionEngine(
        FusionConfig(mode="voice_only", duplicate_command_cooldown_ms=1000, stale_event_timeout_ms=10000)
    )
    now = time.time()
    first = engine.resolve(voice_event=_voice("go"), gesture_event=None, now=now)
    assert first is not None

    second = engine.resolve(voice_event=_voice("go"), gesture_event=None, now=now + 0.1)
    assert second is None

    third = engine.resolve(voice_event=_voice("go"), gesture_event=None, now=now + 2.0)
    assert third is not None


def test_require_confirmation_for_continuous_motion_rejects_single_modality():
    config = FusionConfig(mode="voice_priority", require_confirmation_for=["continuous_motion"])
    engine = FusionEngine(config)

    # "go" -> action "move", which is in the continuous_motion category and
    # therefore needs both modalities to agree - voice alone isn't enough.
    decision = engine.resolve(voice_event=_voice("go"), gesture_event=None)
    assert decision is None

    decision_confirmed = engine.resolve(voice_event=_voice("go"), gesture_event=_gesture("go"))
    assert decision_confirmed is not None


def test_require_confirmation_for_does_not_affect_uncategorized_actions():
    config = FusionConfig(mode="voice_priority", require_confirmation_for=["continuous_motion"])
    engine = FusionEngine(config)

    # "left" -> action "turn", not in the continuous_motion category, so a
    # single modality is still sufficient.
    decision = engine.resolve(voice_event=_voice("left"), gesture_event=None)
    assert decision is not None


def test_unconfirmed_gesture_state_is_not_treated_as_a_command():
    engine = FusionEngine(FusionConfig(mode="gesture_only"))
    decision = engine.resolve(voice_event=None, gesture_event=_gesture("go", state="candidate"))
    assert decision is None


def test_no_events_returns_none():
    engine = FusionEngine(FusionConfig())
    assert engine.resolve(voice_event=None, gesture_event=None) is None
