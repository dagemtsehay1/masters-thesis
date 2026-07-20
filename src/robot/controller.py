import logging

import numpy as np

from src.commands.schema import RobotCommand
from src.config.schema import RobotConfig
from src.robot.safety import SafetyController
from src.utils.math_utils import wrap_to_pi

logger = logging.getLogger("robot.controller")

_TURN_ANGLES = {
    "left": np.pi / 2,
    "right": -np.pi / 2,
    "around": np.pi,
}


class RobotController:
    """State machine translating validated RobotCommands into velocity
    signals. Only ever accepts `RobotCommand` instances - callers are
    responsible for routing everything through `commands.validator` first.

    Every tick, `step()` checks the safety controller before doing anything
    else: an active emergency stop or an expired dead-man timeout both force
    the robot to idle, regardless of what state the movement/rotation state
    machine below thinks it's in.
    """

    def __init__(self, client, safety: SafetyController, config: RobotConfig):
        self.client = client
        self.safety = safety
        self.config = config

        self.state = "idle"   # idle | moving | rotating
        self.mode = "stop"    # forward | backward | stop

        self.target_angle = None
        self.prev_mode = "stop"

        self.linear_speed = config.linear_speed
        self.angular_speed = config.angular_speed

    # ================= COMMAND HANDLER =================

    def handle_command(self, command: RobotCommand):
        logger.info(
            "Handling command: %s/%s (source=%s, confidence=%.2f)",
            command.action,
            command.direction,
            command.source,
            command.confidence,
        )
        self.safety.record_command()

        if command.action in ("stop", "emergency_stop"):
            self.mode = "stop"
            self.state = "idle"
            self._stop_robot()
            if command.action == "emergency_stop":
                self.safety.trigger_emergency_stop(reason="emergency_stop command")
            return

        if command.action == "move":
            self.mode = "backward" if command.direction == "backward" else "forward"
            self.state = "moving"
            return

        if command.action == "turn":
            angle = _TURN_ANGLES.get(command.direction)
            if angle is not None:
                self._start_rotation(angle)
            return

    # ================= ROTATION =================

    def _start_rotation(self, angle):
        ori = self.client.get_orientation()
        current_phi = ori[2]

        self.target_angle = wrap_to_pi(current_phi + angle)
        self.prev_mode = self.mode  # remember previous mode
        self.state = "rotating"

    # ================= MAIN LOOP =================

    def step(self):
        if self.safety.emergency_stop_active:
            if self.state != "idle":
                self._stop_robot()
                self.state = "idle"
                self.mode = "stop"
            return

        if self.state != "idle" and self.safety.dead_man_expired():
            logger.warning("Dead-man timeout expired with no fresh command - stopping robot")
            self._stop_robot()
            self.state = "idle"
            self.mode = "stop"
            return

        if self.state == "moving":
            self._move()

        elif self.state == "rotating":
            self._rotate()

    # ================= MOVE =================

    def _move(self):
        if self.mode == "forward":
            self.client.send_velocity(0, self.linear_speed, 0)

        elif self.mode == "backward":
            self.client.send_velocity(0, -self.linear_speed, 0)

    # ================= ROTATE =================

    def _rotate(self):
        ori = self.client.get_orientation()
        phi = ori[2]

        error = wrap_to_pi(self.target_angle - phi)

        if abs(error) < np.deg2rad(self.config.rotation_tolerance_deg):
            logger.info("Rotation done")

            if self.prev_mode == "forward":
                self.state = "moving"
                self.mode = "forward"

            elif self.prev_mode == "backward":
                self.state = "moving"
                self.mode = "backward"

            else:
                self.state = "idle"
                self.mode = "stop"
                self._stop_robot()

            return

        rot_dir = np.sign(error)
        self.client.send_velocity(0, 0, rot_dir * self.angular_speed)

    # ================= STOP =================

    def _stop_robot(self):
        self.client.send_velocity(0, 0, 0)
