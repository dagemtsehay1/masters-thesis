"""Amharic alias resolution tests.

These check the *plumbing* (Ge'ez-script and transliterated phrases resolve
to the same canonical vocabulary as English, and mixed-language utterances
each route to the right parser) - not Whisper's real-world Amharic accuracy,
which is a measured, hardware-dependent quantity covered by the recording
protocol in docs/amharic_dataset_protocol.md, not by unit tests.
"""
import pytest

from src.intent.intent_engine import IntentEngine
from src.intent.rule_parser import RuleBasedParser
from src.speech.normalizer import normalize_text


@pytest.mark.parametrize(
    "phrase,expected_canonical",
    [
        ("ወደፊት ሂድ", "move_forward"),
        ("ወደ ፊት ተንቀሳቀስ", "move_forward"),
        ("ወደ ግራ ታጠፍ", "turn_left"),
        ("ወደ ቀኝ ታጠፍ", "turn_right"),
        ("ወደ ኋላ ተመለስ", "turn_around"),
        ("ቁም", "stop"),
    ],
)
def test_amharic_script_aliases_resolve(phrase, expected_canonical):
    parser = RuleBasedParser(language="am")
    canonical, confidence = parser.parse(normalize_text(phrase, "am"))
    assert canonical == expected_canonical
    assert confidence > 0.0


@pytest.mark.parametrize(
    "phrase,expected_canonical",
    [
        ("wede fit hid", "move_forward"),
        ("gra", "turn_left"),
        ("kegn", "turn_right"),
        ("temeles", "turn_around"),
        ("kum", "stop"),
    ],
)
def test_amharic_transliterations_resolve(phrase, expected_canonical):
    parser = RuleBasedParser(language="am")
    canonical, _ = parser.parse(normalize_text(phrase, "am"))
    assert canonical == expected_canonical


def test_geez_punctuation_is_normalized_away():
    parser = RuleBasedParser(language="am")
    canonical, _ = parser.parse(normalize_text("ቁም።", "am"))
    assert canonical == "stop"


def test_amharic_and_english_share_the_same_canonical_vocabulary():
    en = RuleBasedParser(language="en")
    am = RuleBasedParser(language="am")
    en_canonical, _ = en.parse(normalize_text("stop", "en"))
    am_canonical, _ = am.parse(normalize_text("ቁም", "am"))
    assert en_canonical == am_canonical == "stop"


def test_intent_engine_dispatches_on_detected_language():
    engine = IntentEngine(
        language="en", enabled_languages=["en", "am"], confidence_threshold=0.4
    )

    english_event = engine.resolve("go forward", transcript_confidence=0.9, language="en")
    amharic_event = engine.resolve("ወደፊት ሂድ", transcript_confidence=0.9, language="am")

    assert english_event is not None and english_event.command == "go"
    assert english_event.language == "en"
    assert amharic_event is not None and amharic_event.command == "go"
    assert amharic_event.language == "am"


def test_mixed_language_session_resolves_each_utterance_independently():
    engine = IntentEngine(
        language="en", enabled_languages=["en", "am"], confidence_threshold=0.4
    )
    sequence = [
        ("stop", "en", "stop"),
        ("ወደ ግራ ታጠፍ", "am", "left"),
        ("advance", "en", "go"),
        ("ቁም", "am", "stop"),
    ]
    for transcript, language, expected_word in sequence:
        event = engine.resolve(transcript, transcript_confidence=0.9, language=language)
        assert event is not None
        assert event.command == expected_word


def test_unclear_amharic_returns_none():
    engine = IntentEngine(
        language="en", enabled_languages=["en", "am"], confidence_threshold=0.4
    )
    assert engine.resolve("ሰላም እንደምን አለህ", transcript_confidence=0.9, language="am") is None
