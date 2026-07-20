import pytest

from src.fusion.modes import MODE_FUNCTIONS
from src.fusion.policy import NormalizedEvent


def _event(value, confidence=0.9, age_s=0.1, source="voice"):
    return NormalizedEvent(value=value, confidence=confidence, age_s=age_s, source=source)


@pytest.mark.parametrize("mode", list(MODE_FUNCTIONS.keys()))
def test_every_mode_returns_none_when_nothing_is_present(mode):
    assert MODE_FUNCTIONS[mode](None, None) is None


def test_voice_only_ignores_gesture():
    voice = _event("go", source="voice")
    gesture = _event("stop", source="gesture")
    assert MODE_FUNCTIONS["voice_only"](voice, gesture) == ("go", "voice", voice.confidence)
    assert MODE_FUNCTIONS["voice_only"](None, gesture) is None


def test_gesture_only_ignores_voice():
    voice = _event("go", source="voice")
    gesture = _event("stop", source="gesture")
    assert MODE_FUNCTIONS["gesture_only"](voice, gesture) == ("stop", "gesture", gesture.confidence)
    assert MODE_FUNCTIONS["gesture_only"](voice, None) is None


def test_either_accepts_whichever_single_modality_is_present():
    voice = _event("go", source="voice")
    assert MODE_FUNCTIONS["either"](voice, None) == ("go", "voice", voice.confidence)
    gesture = _event("left", source="gesture")
    assert MODE_FUNCTIONS["either"](None, gesture) == ("left", "gesture", gesture.confidence)


def test_voice_priority_prefers_voice_when_both_present():
    voice = _event("go", confidence=0.5, source="voice")
    gesture = _event("left", confidence=0.99, source="gesture")
    assert MODE_FUNCTIONS["voice_priority"](voice, gesture)[1] == "voice"


def test_gesture_priority_prefers_gesture_when_both_present():
    voice = _event("go", confidence=0.99, source="voice")
    gesture = _event("left", confidence=0.5, source="gesture")
    assert MODE_FUNCTIONS["gesture_priority"](voice, gesture)[1] == "gesture"


def test_latest_wins_picks_the_smaller_age():
    voice = _event("go", age_s=1.0, source="voice")
    gesture = _event("left", age_s=0.1, source="gesture")
    assert MODE_FUNCTIONS["latest_wins"](voice, gesture)[1] == "gesture"


def test_highest_confidence_picks_the_bigger_confidence():
    voice = _event("go", confidence=0.6, source="voice")
    gesture = _event("left", confidence=0.95, source="gesture")
    assert MODE_FUNCTIONS["highest_confidence"](voice, gesture)[1] == "gesture"


def test_confirmation_requires_both_modalities_to_agree():
    voice = _event("go", source="voice")
    gesture_agree = _event("go", source="gesture")
    gesture_disagree = _event("left", source="gesture")

    resolved = MODE_FUNCTIONS["confirmation"](voice, gesture_agree)
    assert resolved == ("go", "combined", max(voice.confidence, gesture_agree.confidence))

    assert MODE_FUNCTIONS["confirmation"](voice, gesture_disagree) is None
    assert MODE_FUNCTIONS["confirmation"](voice, None) is None


def test_combined_lets_go_and_a_turn_compose():
    voice_go = _event("go", confidence=0.8, source="voice")
    gesture_left = _event("left", confidence=0.9, source="gesture")
    resolved = MODE_FUNCTIONS["combined"](voice_go, gesture_left)
    assert resolved == ("left", "combined", 0.8)

    # Symmetric: gesture "go" + voice "left" also composes.
    voice_left = _event("left", confidence=0.7, source="voice")
    gesture_go = _event("go", confidence=0.6, source="gesture")
    resolved2 = MODE_FUNCTIONS["combined"](voice_left, gesture_go)
    assert resolved2 == ("left", "combined", 0.6)


def test_combined_rejects_incompatible_pairs():
    voice = _event("left", source="voice")
    gesture = _event("right", source="gesture")
    assert MODE_FUNCTIONS["combined"](voice, gesture) is None
