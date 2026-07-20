"""Qwen fallback tests - fully mocked Ollama, no live server required."""
import json

import pytest

from src.config.schema import QwenConfig
from src.intent.qwen_client import QwenClient
from src.intent.schemas import QwenResponse, to_canonical


def test_valid_response_maps_to_canonical():
    response = QwenResponse(action="turn", direction="left", confidence=0.86, reason="user asked to go left")
    assert to_canonical(response) == "turn_left"


def test_stop_response_maps_to_canonical():
    response = QwenResponse(action="stop", direction=None, confidence=0.9)
    assert to_canonical(response) == "stop"


def test_out_of_vocabulary_action_maps_to_none():
    response = QwenResponse(action="dance", direction="left", confidence=0.9)
    assert to_canonical(response) is None


def test_out_of_vocabulary_direction_maps_to_none():
    response = QwenResponse(action="move", direction="sideways", confidence=0.9)
    assert to_canonical(response) is None


def test_extra_fields_are_rejected_by_schema():
    with pytest.raises(Exception):
        QwenResponse(action="move", direction="forward", confidence=0.9, hacked=True)


def _mock_generate(monkeypatch, model_text):
    """Patch urllib so QwenClient's HTTP call returns model_text as the
    Ollama /api/generate 'response' body."""
    import src.intent.qwen_client as qc

    class _FakeResponse:
        status = 200

        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps({"response": self._payload}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        return _FakeResponse(model_text)

    monkeypatch.setattr(qc.urllib.request, "urlopen", fake_urlopen)


def _client(enabled=True):
    return QwenClient(QwenConfig(enabled=enabled))


def test_disabled_client_never_resolves():
    client = _client(enabled=False)
    assert client.resolve("advance") == (None, 0.0)


def test_client_resolves_valid_json_response(monkeypatch):
    _mock_generate(monkeypatch, json.dumps({"action": "move", "direction": "forward", "confidence": 0.8}))
    canonical, confidence = _client().resolve("move ahead please")
    assert canonical == "move_forward"
    assert confidence == pytest.approx(0.8)


def test_client_rejects_malformed_json(monkeypatch):
    _mock_generate(monkeypatch, "this is not json")
    assert _client().resolve("some command") == (None, 0.0)


def test_client_rejects_out_of_vocabulary_response(monkeypatch):
    _mock_generate(monkeypatch, json.dumps({"action": "explode", "direction": None, "confidence": 0.99}))
    assert _client().resolve("self destruct") == (None, 0.0)


def test_client_does_not_resolve_for_unconfigured_language(monkeypatch):
    _mock_generate(monkeypatch, json.dumps({"action": "move", "direction": "forward", "confidence": 0.9}))
    # Default config only lists English; Amharic must not be routed to Qwen.
    assert _client().resolve("some command", language="am") == (None, 0.0)


def test_health_check_handles_unreachable_server(monkeypatch):
    import src.intent.qwen_client as qc

    def fake_urlopen(request, timeout=None):
        raise qc.urllib.error.URLError("connection refused")

    monkeypatch.setattr(qc.urllib.request, "urlopen", fake_urlopen)
    assert _client().health_check() is False
