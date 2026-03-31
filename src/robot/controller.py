import numpy as np
from src.utils.math_utils import wrap_to_pi


class RobotController:
    def __init__(self, client):
        self.client = client

        self.state = "idle"   # idle | moving | rotating
        self.mode = "stop"    # forward | backward | stop

        self.target_angle = None

        # self.linear_speed = 0.5
        self.linear_speed = 2.0
        # self.angular_speed = 1.0
        self.angular_speed = 2.0

    # ================= COMMAND HANDLER =================

    def handle_command(self, command: str):
        print(f"🎯 Handling: {command}")

        if command == "go":
            self.mode = "forward"
            self.state = "moving"

        elif command == "stop":
            self.mode = "stop"
            self.state = "idle"
            self._stop_robot()

        elif command == "left":
            self._start_rotation(np.pi / 2)

        elif command == "right":
            self._start_rotation(-np.pi / 2)

        elif command == "back":
            self._start_rotation(np.pi)

    # ================= ROTATION =================

    def _start_rotation(self, angle):
        ori = self.client.get_orientation()
        current_phi = ori[2]

        self.target_angle = wrap_to_pi(current_phi + angle)

        self.prev_mode = self.mode  # remember previous mode
        self.state = "rotating"

    # ================= MAIN LOOP =================

    def step(self):
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

        if abs(error) < np.deg2rad(3):
            print("✅ Rotation done")

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