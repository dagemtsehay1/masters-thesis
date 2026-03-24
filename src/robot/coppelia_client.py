from coppeliasim_zmqremoteapi_client import RemoteAPIClient


class CoppeliaClient:
    def __init__(self):
        print("🔌 Connecting to CoppeliaSim...")

        client = RemoteAPIClient()
        self.sim = client.getObject('sim')

        # ✅ TEST CONNECTION
        sim_time = self.sim.getSimulationTime()
        print(f"✅ Connected! Simulation time: {sim_time}")

        # robot handle
        self.robot = self.sim.getObject('/youBot')
        print("✅ Robot found:", self.robot)
        client = RemoteAPIClient()
        self.sim = client.getObject('sim')

        # CHANGE THESE based on your robot
        self.robot = self.sim.getObject('/youBot')

    def get_position(self):
        return self.sim.getObjectPosition(self.robot, -1)

    def get_orientation(self):
        return self.sim.getObjectOrientation(self.robot, -1)

    def send_velocity(self, leftRightVel, forwBackVel, rotVel):
        self.sim.setFloatSignal('leftRightVel', leftRightVel)
        self.sim.setFloatSignal('forwBackVel', forwBackVel)
        self.sim.setFloatSignal('rotVel', rotVel)