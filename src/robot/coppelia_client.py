import logging

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

logger = logging.getLogger("robot.coppelia_client")


class CoppeliaClient:
    """Thin wrapper around the CoppeliaSim ZeroMQ remote API.

    Owns exactly one connection and one robot object handle - nothing else
    in the app should talk to CoppeliaSim directly.
    """

    def __init__(self, host: str = "localhost", port: int = 23000, robot_object: str = "/youBot"):
        self._host = host
        self._port = port
        self._robot_path = robot_object

        self.sim = None
        self.robot = None
        self.connect()

    def connect(self) -> None:
        logger.info("Connecting to CoppeliaSim at %s:%s...", self._host, self._port)

        client = RemoteAPIClient(host=self._host, port=self._port)
        self.sim = client.getObject("sim")

        sim_time = self.sim.getSimulationTime()
        logger.info("Connected. Simulation time: %s", sim_time)

        self.robot = self.sim.getObject(self._robot_path)
        logger.info("Robot object found: %s", self.robot)

    def is_connected(self) -> bool:
        if self.sim is None:
            return False
        try:
            self.sim.getSimulationTime()
            return True
        except Exception:
            return False

    def get_position(self):
        return self.sim.getObjectPosition(self.robot, -1)

    def get_orientation(self):
        return self.sim.getObjectOrientation(self.robot, -1)

    def send_velocity(self, leftRightVel, forwBackVel, rotVel):
        self.sim.setFloatSignal("leftRightVel", float(leftRightVel))
        self.sim.setFloatSignal("forwBackVel", float(forwBackVel))
        self.sim.setFloatSignal("rotVel", float(rotVel))
