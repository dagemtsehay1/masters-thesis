"""Verifies the intent-engine tier ordering: the Qwen fallback is only ever
consulted when the deterministic alias/fuzzy tiers fail to resolve."""
from src.intent.intent_engine import IntentEngine


class SpyQwenClient:
    def __init__(self, canonical=None, confidence=0.0):
        self.enabled = True
        self._canonical = canonical
        self._confidence = confidence
        self.calls = 0

    def resolve(self, normalized_text, language="en"):
        self.calls += 1
        return self._canonical, self._confidence


def test_qwen_not_called_when_rules_resolve():
    spy = SpyQwenClient(canonical="stop", confidence=0.9)
    engine = IntentEngine(language="en", confidence_threshold=0.4, qwen_client=spy)

    event = engine.resolve("go forward", transcript_confidence=0.9)
    assert event is not None
    assert event.command == "go"
    assert spy.calls == 0  # rules resolved it; Qwen never consulted


def test_qwen_called_only_when_rules_fail():
    spy = SpyQwenClient(canonical="turn_left", confidence=0.85)
    engine = IntentEngine(language="en", confidence_threshold=0.4, qwen_client=spy)

    event = engine.resolve("swing to the port side", transcript_confidence=0.9)
    assert spy.calls == 1
    assert event is not None
    assert event.command == "left"


def test_disabled_qwen_is_not_consulted():
    spy = SpyQwenClient(canonical="stop", confidence=0.9)
    spy.enabled = False
    engine = IntentEngine(language="en", confidence_threshold=0.4, qwen_client=spy)

    event = engine.resolve("gibberish that matches nothing", transcript_confidence=0.9)
    assert event is None
    assert spy.calls == 0


def test_no_qwen_client_still_works_for_rule_matches():
    engine = IntentEngine(language="en", confidence_threshold=0.4, qwen_client=None)
    event = engine.resolve("stop", transcript_confidence=0.9)
    assert event is not None
    assert event.command == "stop"
