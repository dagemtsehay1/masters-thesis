import time

from src.config.schema import SafetyConfig
from src.robot.safety import SafetyController


def test_emergency_stop_trigger_and_clear():
    safety = SafetyController(SafetyConfig())
    assert not safety.emergency_stop_active

    safety.trigger_emergency_stop(reason="test")
    assert safety.emergency_stop_active

    safety.clear_emergency_stop()
    assert not safety.emergency_stop_active


def test_dead_man_not_expired_before_any_command():
    safety = SafetyController(SafetyConfig(dead_man_timeout_s=0.05))
    # No command has ever been recorded - nothing to time out yet.
    assert not safety.dead_man_expired()


def test_dead_man_not_expired_immediately_after_command():
    safety = SafetyController(SafetyConfig(dead_man_timeout_s=1.0))
    safety.record_command()
    assert not safety.dead_man_expired()


def test_dead_man_expires_after_timeout():
    safety = SafetyController(SafetyConfig(dead_man_timeout_s=0.05))
    safety.record_command()
    time.sleep(0.08)
    assert safety.dead_man_expired()


def test_fresh_command_resets_dead_man_timer():
    safety = SafetyController(SafetyConfig(dead_man_timeout_s=0.05))
    safety.record_command()
    time.sleep(0.08)
    assert safety.dead_man_expired()

    safety.record_command()
    assert not safety.dead_man_expired()
