import time

import numpy as np
import pytest

from src.commands.schema import RobotCommand
from src.config.schema import RobotConfig, SafetyConfig
from src.robot.controller import RobotController
from src.robot.safety import SafetyController


class FakeCoppeliaClient:
    """Minimal stand-in for CoppeliaClient - no real simulator needed."""

    def __init__(self, orientation=(0.0, 0.0, 0.0)):
        self.orientation = list(orientation)
        self.velocity_calls = []

    def get_orientation(self):
        return self.orientation

    def send_velocity(self, left_right, forw_back, rot):
        self.velocity_calls.append((left_right, forw_back, rot))


def make_controller(dead_man_timeout_s=3.0):
    client = FakeCoppeliaClient()
    safety = SafetyController(SafetyConfig(dead_man_timeout_s=dead_man_timeout_s))
    controller = RobotController(client, safety, RobotConfig())
    return controller, client, safety


def test_move_forward_sends_positive_linear_velocity():
    controller, client, _ = make_controller()
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    controller.step()

    assert controller.state == "moving"
    assert client.velocity_calls[-1] == (0, controller.linear_speed, 0)


def test_stop_command_halts_movement():
    controller, client, _ = make_controller()
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    controller.handle_command(RobotCommand(action="stop", source="voice"))

    assert controller.state == "idle"
    assert client.velocity_calls[-1] == (0, 0, 0)


def test_turn_left_starts_rotation_towards_target_angle():
    controller, client, _ = make_controller()
    controller.handle_command(RobotCommand(action="turn", direction="left", source="gesture"))

    assert controller.state == "rotating"
    assert controller.target_angle == pytest.approx(np.pi / 2)


def test_rotation_completes_and_resumes_forward_motion():
    controller, client, _ = make_controller()
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    controller.handle_command(RobotCommand(action="turn", direction="right", source="voice"))
    assert controller.state == "rotating"

    # Simulate the robot having reached the target orientation.
    client.orientation[2] = controller.target_angle
    controller.step()

    assert controller.state == "moving"
    assert controller.mode == "forward"


def test_emergency_stop_forces_idle_even_while_moving():
    controller, client, safety = make_controller()
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    safety.trigger_emergency_stop(reason="test")
    controller.step()

    assert controller.state == "idle"
    assert client.velocity_calls[-1] == (0, 0, 0)


def test_dead_man_timeout_auto_stops_continuous_motion():
    controller, client, _ = make_controller(dead_man_timeout_s=0.05)
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    time.sleep(0.08)
    controller.step()

    assert controller.state == "idle"
    assert client.velocity_calls[-1] == (0, 0, 0)
