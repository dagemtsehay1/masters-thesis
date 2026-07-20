"""Manual smoke test - not part of the pytest suite.

Drives the youBot forward for a few seconds directly through the raw
RemoteAPIClient, bypassing the app's own CoppeliaClient/RobotController.
Useful for sanity-checking that a CoppeliaSim scene is reachable and its
velocity signals respond, independent of the voice/gesture stack.

Run against a live CoppeliaSim session with scene/scene01.ttt loaded and
the simulation running:

    uv run python tests/manual/smoke_coppelia.py
"""
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
