import time
from coppeliasim_zmqremoteapi_client import RemoteAPIClient

client = RemoteAPIClient()
sim = client.getObject('sim')

for _ in range(100):
    sim.setFloatSignal("leftRightVel", 0.0)
    sim.setFloatSignal("forwBackVel", 2.0)
    sim.setFloatSignal("rotVel", 0.0)
    time.sleep(0.05)

sim.setFloatSignal("leftRightVel", 0.0)
sim.setFloatSignal("forwBackVel", 0.0)
sim.setFloatSignal("rotVel", 0.0)