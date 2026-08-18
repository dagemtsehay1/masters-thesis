import logging
import time
from typing import Optional

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

logger = logging.getLogger("robot.coppelia_client")


class CoppeliaClient:
    """Thin wrapper around the CoppeliaSim ZeroMQ remote API.

    Owns exactly one connection and one robot object handle - nothing else
    in the app should talk to CoppeliaSim directly.

    Connection failure does not raise. CoppeliaSim is frequently still
    starting up (or not open yet) when the Python app is launched, and
    voice/gesture recognition have nothing to do with the simulator
    connection (see the architecture note that perception must be testable
    without robot motion). So `connect()` retries a configured number of
    times and, if it still can't reach CoppeliaSim, leaves the client in a
    "disconnected" state instead of raising - `start_services()` can then
    go on to start voice/gesture normally, and every motion call below
    becomes a logged no-op until `reconnect()` succeeds.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 23000,
        robot_object: str = "/youBot",
        retry_attempts: int = 3,
        retry_delay_s: float = 1.0,
    ):
        self._host = host
        self._port = port
        self._robot_path = robot_object
        self._retry_attempts = max(1, retry_attempts)
        self._retry_delay_s = max(0.0, retry_delay_s)

        self.sim = None
        self.robot = None
        self._last_warning_time = 0.0
        self.connect()

    def connect(self) -> bool:
        """Attempts to (re)connect, retrying up to `retry_attempts` times.
        Returns True on success. Never raises - a failure is logged and
        leaves `sim`/`robot` as None so the rest of the app can keep going
        without a live simulator connection."""
        for attempt in range(1, self._retry_attempts + 1):
            try:
                logger.info(
                    "Connecting to CoppeliaSim at %s:%s (attempt %d/%d)...",
                    self._host, self._port, attempt, self._retry_attempts,
                )
                client = RemoteAPIClient(host=self._host, port=self._port)
                sim = client.getObject("sim")
                sim_time = sim.getSimulationTime()
                robot = sim.getObject(self._robot_path)

                self.sim = sim
                self.robot = robot
                logger.info("Connected. Simulation time: %s, robot object: %s", sim_time, robot)
                return True
            except Exception as exc:
                logger.warning(
                    "CoppeliaSim connection attempt %d/%d failed: %s", attempt, self._retry_attempts, exc
                )
                if attempt < self._retry_attempts:
                    time.sleep(self._retry_delay_s)

        self.sim = None
        self.robot = None
        logger.error(
            "Could not connect to CoppeliaSim at %s:%s after %d attempt(s). "
            "Robot motion will be a no-op until reconnected (voice/gesture recognition are unaffected).",
            self._host, self._port, self._retry_attempts,
        )
        return False

    def reconnect(self) -> bool:
        """Re-attempts the connection on demand (e.g. a "Reconnect" UI action
        once the user has started CoppeliaSim)."""
        return self.connect()

    def set_endpoint(self, host: str, port: int, robot_object: Optional[str] = None) -> None:
        """Updates the connection target for the next `reconnect()` call -
        used by the Configuration panel's CoppeliaSim host/port fields.
        Does not itself reconnect."""
        self._host = host
        self._port = int(port)
        if robot_object:
            self._robot_path = robot_object

    def is_connected(self) -> bool:
        if self.sim is None:
            return False
        try:
            self.sim.getSimulationTime()
            return True
        except Exception:
            return False

    def _warn_disconnected(self, operation: str) -> None:
        # Rate-limited so a continuous motion command being polled every
        # ~50ms doesn't flood the log while disconnected.
        now = time.monotonic()
        if now - self._last_warning_time > 2.0:
            logger.warning("CoppeliaSim is not connected - ignoring %s", operation)
            self._last_warning_time = now

    def get_position(self):
        if self.sim is None:
            self._warn_disconnected("get_position()")
            return (0.0, 0.0, 0.0)
        return self.sim.getObjectPosition(self.robot, -1)

    def get_orientation(self):
        if self.sim is None:
            self._warn_disconnected("get_orientation()")
            return (0.0, 0.0, 0.0)
        return self.sim.getObjectOrientation(self.robot, -1)

    def send_velocity(self, leftRightVel, forwBackVel, rotVel):
        if self.sim is None:
            self._warn_disconnected("send_velocity()")
            return
        self.sim.setFloatSignal("leftRightVel", float(leftRightVel))
        self.sim.setFloatSignal("forwBackVel", float(forwBackVel))
        self.sim.setFloatSignal("rotVel", float(rotVel))
