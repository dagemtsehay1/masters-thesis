"""The single gate every command must pass before it can reach the robot.

Voice, gesture, and manual UI input all funnel through `CommandValidator`.
It rejects malformed input (enforced structurally by `RobotCommand`'s own
schema), anything outside the whitelist in `registry.py`, and clamps
speed/duration to the configured safety limits rather than trusting
detector output directly.
"""
import logging
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from src.commands.registry import is_allowed
from src.commands.schema import RobotCommand
from src.config.schema import RobotConfig, SafetyConfig

logger = logging.getLogger("commands.validator")


@dataclass
class ValidationResult:
    accepted: bool
    command: Optional[RobotCommand] = None
    reason: Optional[str] = None


class CommandValidator:
    def __init__(self, robot_config: RobotConfig, safety_config: SafetyConfig):
        self._robot_config = robot_config
        self._safety_config = safety_config

    def validate(self, candidate: Any) -> ValidationResult:
        if isinstance(candidate, RobotCommand):
            command = candidate
        else:
            try:
                command = RobotCommand(**candidate)
            except (ValidationError, TypeError) as exc:
                return ValidationResult(False, reason=f"malformed command: {exc}")

        if command.action not in self._safety_config.allowed_actions:
            return ValidationResult(
                False, reason=f"action '{command.action}' is not in the allowed-action whitelist"
            )

        if not is_allowed(command.action, command.direction):
            return ValidationResult(
                False,
                reason=f"'{command.action}'/'{command.direction}' is not a recognized command",
            )

        clamped = command.model_copy()
        if clamped.speed is not None:
            limit = (
                self._robot_config.max_linear_speed
                if command.action == "move"
                else self._robot_config.max_angular_speed
            )
            clamped.speed = max(0.0, min(clamped.speed, limit))

        if clamped.duration is not None and self._robot_config.max_command_duration_s is not None:
            clamped.duration = min(clamped.duration, self._robot_config.max_command_duration_s)

        return ValidationResult(True, command=clamped)
