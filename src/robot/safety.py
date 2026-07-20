"""The runtime safety gate between validated commands and the robot.

Owns the emergency-stop flag and the dead-man timeout that guards against
unattended continuous motion. This is intentionally the *only* thing
`RobotController.step()` consults before acting - it must keep working even
if voice, gesture, or the simulator connection have already failed, which is
why it holds no reference to any of them.
"""
import logging
import time
from typing import Optional

from src.config.schema import SafetyConfig

logger = logging.getLogger("robot.safety")


class SafetyController:
    def __init__(self, config: SafetyConfig):
        self._config = config
        self._emergency_stop_active = False
        self._last_command_time: Optional[float] = None

    @property
    def emergency_stop_active(self) -> bool:
        return self._emergency_stop_active

    def trigger_emergency_stop(self, reason: str = "") -> None:
        if not self._emergency_stop_active:
            logger.warning("Emergency stop triggered%s", f": {reason}" if reason else "")
        self._emergency_stop_active = True

    def clear_emergency_stop(self) -> None:
        if self._emergency_stop_active:
            logger.info("Emergency stop cleared")
        self._emergency_stop_active = False

    def record_command(self) -> None:
        """Call whenever a validated command is about to be executed - this
        is the heartbeat the dead-man timeout measures against."""
        self._last_command_time = time.monotonic()

    def dead_man_expired(self) -> bool:
        """True once continuous motion should be halted because no fresh
        command has arrived within `safety.dead_man_timeout_s`."""
        if self._last_command_time is None:
            return False
        return (time.monotonic() - self._last_command_time) > self._config.dead_man_timeout_s
