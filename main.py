import time

from src.voice.detector import VoiceCommandDetector
from src.robot.coppelia_client import CoppeliaClient
from src.robot.controller import RobotController


def main():
    # ================= INIT =================
    voice = VoiceCommandDetector(model_path="model")
    client = CoppeliaClient()
    controller = RobotController(client)

    print("🚀 System started")
    print("🎤 Say: go, stop, left, right, back")

    # ================= MAIN LOOP =================
    with voice.start_stream():
        while True:
            try:
                # 🎤 get voice command
                command = voice.listen()

                if command:
                    print(f"✅ Command: {command}")
                    controller.handle_command(command)

                # 🤖 update robot
                controller.step()

                time.sleep(0.05)

            except KeyboardInterrupt:
                print("\n🛑 Stopping system...")
                controller._stop_robot()
                break

            except Exception as e:
                print(f"❌ Error: {e}")
                controller._stop_robot()


if __name__ == "__main__":
    main()