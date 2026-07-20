"""Health-check tests using a fake Application-like object, so they run
without any real hardware or services."""
from types import SimpleNamespace

from src.monitoring import health


def _fake_app(**overrides):
    defaults = dict(
        config=SimpleNamespace(
            gesture=SimpleNamespace(enabled=True),
            voice=SimpleNamespace(enabled=True),
            speech=SimpleNamespace(whisper=SimpleNamespace(model="small")),
            intent=SimpleNamespace(qwen=SimpleNamespace(enabled=False)),
        ),
        gesture=object(),
        voice=object(),
        qwen_client=None,
        client=SimpleNamespace(is_connected=lambda: True),
        controller=SimpleNamespace(_stop_robot=lambda: None),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_all_checks_pass_when_everything_is_up():
    results = health.run_all(_fake_app())
    by_name = {r.name: r.status for r in results}
    assert by_name["camera"] == "pass"
    assert by_name["microphone"] == "pass"
    assert by_name["whisper"] == "pass"
    assert by_name["coppelia"] == "pass"
    assert by_name["robot_stop"] == "pass"
    # Qwen disabled -> a warn, not a fail.
    assert by_name["ollama"] == "warn"


def test_disconnected_simulator_fails():
    app = _fake_app(client=SimpleNamespace(is_connected=lambda: False))
    result = health.check_coppelia(app)
    assert result.status == "fail"


def test_missing_controller_fails_robot_stop():
    app = _fake_app(controller=None)
    result = health.check_robot_stop(app)
    assert result.status == "fail"


def test_robot_stop_check_only_sends_stop_never_moves():
    calls = []
    app = _fake_app(controller=SimpleNamespace(_stop_robot=lambda: calls.append("stop")))
    result = health.check_robot_stop(app)
    assert result.status == "pass"
    assert calls == ["stop"]  # only a stop, no movement command
