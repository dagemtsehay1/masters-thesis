import time

import numpy as np
import pytest

from src.commands.schema import RobotCommand
from src.config.schema import RobotConfig, SafetyConfig
from src.robot.controller import RobotController
from src.robot.safety import SafetyController
from src.utils.math_utils import wrap_to_pi


class FakeCoppeliaClient:
    """Minimal stand-in for CoppeliaClient - no real simulator needed."""

    def __init__(self, orientation=(0.0, 0.0, 0.0)):
        self.orientation = list(orientation)
        self.velocity_calls = []

    def get_orientation(self):
        return self.orientation

    def send_velocity(self, left_right, forw_back, rot):
        self.velocity_calls.append((left_right, forw_back, rot))


class SimulatedYawClient(FakeCoppeliaClient):
    """Integrates yaw from the commanded rotational velocity between ticks,
    the way CoppeliaSim's physics would - unlike FakeCoppeliaClient (whose
    orientation is inert unless a test pokes it directly), this is what lets
    a test observe whether the *approach* control (send_velocity calls over
    many ticks) actually converges on the target instead of overshooting
    it, not just whether the target angle was computed correctly."""

    def tick(self, dt: float) -> None:
        _, _, last_rot_vel = self.velocity_calls[-1] if self.velocity_calls else (0.0, 0.0, 0.0)
        self.orientation[2] = wrap_to_pi(self.orientation[2] + last_rot_vel * dt)


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


def test_dead_man_timeout_does_not_stop_continuous_movement():
    # By design: a "move forward" command runs indefinitely once issued -
    # it is not auto-stopped just because no further command follows it.
    # Only an explicit stop/emergency_stop command (or the rotation
    # dead-man check below) halts it.
    controller, client, _ = make_controller(dead_man_timeout_s=0.05)
    controller.handle_command(RobotCommand(action="move", direction="forward", source="voice"))
    time.sleep(0.08)
    controller.step()

    assert controller.state == "moving"
    assert client.velocity_calls[-1] == (0, controller.linear_speed, 0)


def test_dead_man_timeout_still_stops_stalled_rotation():
    # Rotation is not open-ended the way translation is - it's supposed to
    # self-terminate once the target angle is reached, so the dead-man
    # timeout still guards against orientation feedback stalling mid-turn.
    controller, client, _ = make_controller(dead_man_timeout_s=0.05)
    controller.handle_command(RobotCommand(action="turn", direction="left", source="voice"))
    time.sleep(0.08)
    controller.step()

    assert controller.state == "idle"
    assert client.velocity_calls[-1] == (0, 0, 0)


@pytest.mark.parametrize(
    "direction, expected_delta_deg",
    [("left", 90.0), ("right", -90.0), ("around", 180.0)],
)
def test_rotation_converges_on_exact_target_angle(direction, expected_delta_deg):
    """LEFT/RIGHT/TURN_AROUND must land on exactly +90/-90/180 degrees
    relative to the orientation the turn started from. A naive constant-
    speed approach can overshoot a narrow tolerance band in a single
    simulation step and settle several degrees off target; the controller's
    deceleration-on-approach (see _ROTATION_DECEL_ZONE_DEG in
    src/robot/controller.py) exists specifically to prevent that."""
    client = SimulatedYawClient()
    safety = SafetyController(SafetyConfig())
    config = RobotConfig()
    controller = RobotController(client, safety, config)

    controller.handle_command(RobotCommand(action="turn", direction=direction, source="voice"))
    # target_angle is wrap_to_pi'd, so +180 deg (turn_around, starting from
    # 0) comes back as -180 deg - the same physical orientation, just the
    # other end of the (-180, 180] representation. abs(wrap_to_pi(...))
    # normalizes that boundary case away for the assertion below.
    target_deg = np.degrees(controller.target_angle)
    assert abs(target_deg) == pytest.approx(abs(expected_delta_deg), abs=1e-6)

    dt = 0.05  # matches RobotWorker's real tick interval
    for _ in range(2000):
        if controller.state != "rotating":
            break
        controller.step()
        client.tick(dt)
    else:
        pytest.fail("rotation never converged within 2000 ticks")

    assert controller.state == "idle"
    final_deg = np.degrees(client.orientation[2])
    assert final_deg == pytest.approx(target_deg, abs=config.rotation_tolerance_deg)
