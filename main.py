import time

from src.voice.detector import VoiceCommandDetector
from src.robot.coppelia_client import CoppeliaClient
from src.robot.controller import RobotController
from src.gesture.detector import GestureDetector


# 🎯 PRIORITY CONTROL
VOICE_PRIORITY = 0.7
GESTURE_PRIORITY = 1 - VOICE_PRIORITY


def main():
    # ================= INIT =================
    voice = VoiceCommandDetector(model_path="model")
    gesture = GestureDetector()

    client = CoppeliaClient()
    controller = RobotController(client)

    gesture.start()

    print("🚀 System started")
    print("🎤 Voice + ✋ Gesture enabled")

    # ================= MAIN LOOP =================
    with voice.start_stream():
        while True:
            try:
                voice_cmd = voice.listen()
                gesture_cmd = gesture.detect()

                final_command = None

                # 🎯 PRIORITY LOGIC
                if voice_cmd and gesture_cmd:
                    final_command = (
                        voice_cmd
                        if VOICE_PRIORITY >= GESTURE_PRIORITY
                        else gesture_cmd
                    )
                elif voice_cmd:
                    final_command = voice_cmd
                elif gesture_cmd:
                    final_command = gesture_cmd

                if final_command:
                    print(f"✅ Command: {final_command}")
                    controller.handle_command(final_command)

                controller.step()
                time.sleep(0.05)

            except KeyboardInterrupt:
                print("\n🛑 Stopping system...")
                controller._stop_robot()
                gesture.stop()
                break

            except Exception as e:
                print(f"❌ Error: {e}")
                controller._stop_robot()


if __name__ == "__main__":
    main()