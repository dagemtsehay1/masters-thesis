import pytest

from src.intent.intent_engine import IntentEngine
from src.intent.rule_parser import RuleBasedParser
from src.speech.normalizer import normalize_text


@pytest.mark.parametrize(
    "phrase,expected_canonical",
    [
        ("move forward", "move_forward"),
        ("go forward", "move_forward"),
        ("advance", "move_forward"),
        ("turn left", "turn_left"),
        ("go left", "turn_left"),
        ("turn right", "turn_right"),
        ("turn around", "turn_around"),
        ("go back", "turn_around"),
        ("stop", "stop"),
        ("halt", "stop"),
    ],
)
def test_english_aliases_resolve_to_canonical(phrase, expected_canonical):
    parser = RuleBasedParser(language="en")
    canonical, confidence = parser.parse(normalize_text(phrase, "en"))
    assert canonical == expected_canonical
    assert confidence > 0.0


def test_punctuation_and_case_are_normalized_away():
    parser = RuleBasedParser(language="en")
    canonical, _ = parser.parse(normalize_text("Stop!", "en"))
    assert canonical == "stop"


def test_fuzzy_matching_tolerates_minor_asr_errors():
    parser = RuleBasedParser(language="en")
    # "advace" is a plausible one-character ASR slip for "advance".
    canonical, confidence = parser.parse(normalize_text("advace", "en"))
    assert canonical == "move_forward"
    assert 0.0 < confidence <= 1.0


def test_unrecognized_phrase_returns_none():
    parser = RuleBasedParser(language="en")
    canonical, confidence = parser.parse(normalize_text("make me a sandwich", "en"))
    assert canonical is None
    assert confidence == 0.0


def test_intent_engine_produces_a_voice_event_with_legacy_command_word():
    engine = IntentEngine(language="en", confidence_threshold=0.4)
    event = engine.resolve("go forward", transcript_confidence=0.9)
    assert event is not None
    assert event.command == "go"  # canonical move_forward -> legacy "go"
    assert event.language == "en"


def test_intent_engine_rejects_below_confidence_threshold():
    engine = IntentEngine(language="en", confidence_threshold=0.9)
    # Transcript confidence caps the combined confidence below the threshold.
    event = engine.resolve("go forward", transcript_confidence=0.2)
    assert event is None


def test_intent_engine_returns_none_for_unrecognized_text():
    engine = IntentEngine(language="en", confidence_threshold=0.4)
    assert engine.resolve("what time is it", transcript_confidence=0.9) is None
