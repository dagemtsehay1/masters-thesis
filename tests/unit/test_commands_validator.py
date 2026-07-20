import pytest

from src.commands.adapters import command_from_legacy_string
from src.commands.schema import RobotCommand
from src.commands.validator import CommandValidator
from src.config.schema import RobotConfig, SafetyConfig


@pytest.fixture
def validator():
    return CommandValidator(RobotConfig(), SafetyConfig())


@pytest.mark.parametrize(
    "legacy_text,expected_action,expected_direction",
    [
        ("go", "move", "forward"),
        ("stop", "stop", None),
        ("left", "turn", "left"),
        ("right", "turn", "right"),
        ("back", "turn", "around"),
    ],
)
def test_legacy_adapter_maps_known_words(legacy_text, expected_action, expected_direction):
    command = command_from_legacy_string(legacy_text, source="voice")
    assert command is not None
    assert command.action == expected_action
    assert command.direction == expected_direction
    assert command.source == "voice"


def test_legacy_adapter_returns_none_for_unknown_word():
    assert command_from_legacy_string("banana", source="voice") is None


def test_validator_accepts_known_commands(validator):
    for text in ["go", "stop", "left", "right", "back"]:
        candidate = command_from_legacy_string(text, source="gesture")
        result = validator.validate(candidate)
        assert result.accepted, result.reason


def test_validator_rejects_command_outside_whitelist(validator):
    bad = RobotCommand(action="move", direction="left", source="manual")  # move+left isn't in the registry
    result = validator.validate(bad)
    assert not result.accepted
    assert "not a recognized command" in result.reason


def test_validator_rejects_action_outside_allowed_actions():
    restricted = CommandValidator(RobotConfig(), SafetyConfig(allowed_actions=["stop"]))
    candidate = command_from_legacy_string("go", source="voice")
    result = restricted.validate(candidate)
    assert not result.accepted
    assert "whitelist" in result.reason


def test_validator_rejects_malformed_dict(validator):
    result = validator.validate({"action": "not_a_real_action", "source": "voice"})
    assert not result.accepted
    assert "malformed" in result.reason


def test_validator_clamps_speed_to_configured_limit():
    validator = CommandValidator(RobotConfig(max_linear_speed=1.0), SafetyConfig())
    candidate = RobotCommand(action="move", direction="forward", source="manual", speed=5.0)
    result = validator.validate(candidate)
    assert result.accepted
    assert result.command.speed == pytest.approx(1.0)


def test_validator_clamps_duration_to_configured_limit():
    validator = CommandValidator(RobotConfig(max_command_duration_s=2.0), SafetyConfig())
    candidate = RobotCommand(action="move", direction="forward", source="manual", duration=10.0)
    result = validator.validate(candidate)
    assert result.accepted
    assert result.command.duration == pytest.approx(2.0)
