"""Component health checks used by the diagnostics panel.

Each check returns a `HealthResult(pass/warn/fail, message)` and must never
raise or move the robot - the robot-stop check sends a zero-velocity
command (which is safe), but no check performs actual robot *movement*.
Movement tests are a separate, explicit user action in the diagnostics
panel, not part of the health check.
"""
from dataclasses import dataclass
from typing import Literal, Optional

Status = Literal["pass", "warn", "fail"]


@dataclass
class HealthResult:
    name: str
    status: Status
    message: str = ""


def check_camera(application) -> HealthResult:
    if not application.config.gesture.enabled:
        return HealthResult("camera", "warn", "Gesture pipeline disabled")
    if application.gesture is None:
        return HealthResult("camera", "fail", "Gesture pipeline not started")
    return HealthResult("camera", "pass", "Camera pipeline running")


def check_microphone(application) -> HealthResult:
    if not application.config.voice.enabled:
        return HealthResult("microphone", "warn", "Voice pipeline disabled")
    if application.voice is None:
        return HealthResult("microphone", "fail", "Voice pipeline not started")
    return HealthResult("microphone", "pass", "Voice pipeline running")


def check_whisper(application) -> HealthResult:
    if not application.config.voice.enabled:
        return HealthResult("whisper", "warn", "Voice pipeline disabled")
    if application.voice is None:
        return HealthResult("whisper", "fail", "Whisper not loaded")
    return HealthResult("whisper", "pass", f"Model '{application.config.speech.whisper.model}' loaded")


def check_ollama(application) -> HealthResult:
    if not application.config.intent.qwen.enabled:
        return HealthResult("ollama", "warn", "Qwen fallback disabled")
    if application.qwen_client is None:
        return HealthResult("ollama", "fail", "Qwen client not created")
    reachable = application.qwen_client.health_check()
    if reachable:
        return HealthResult("ollama", "pass", "Ollama reachable")
    return HealthResult("ollama", "fail", "Ollama not reachable")


def check_coppelia(application) -> HealthResult:
    if application.client is None:
        return HealthResult("coppelia", "fail", "Not connected")
    if application.client.is_connected():
        return HealthResult("coppelia", "pass", "Connected")
    return HealthResult("coppelia", "fail", "Connection lost")


def check_robot_stop(application) -> HealthResult:
    """Sends a zero-velocity (stop) command - safe, never moves the robot."""
    if application.controller is None:
        return HealthResult("robot_stop", "fail", "Controller not started")
    try:
        application.controller._stop_robot()
        return HealthResult("robot_stop", "pass", "Stop command accepted")
    except Exception as exc:
        return HealthResult("robot_stop", "fail", f"Stop command failed: {exc}")


ALL_CHECKS = [
    check_camera,
    check_microphone,
    check_whisper,
    check_ollama,
    check_coppelia,
    check_robot_stop,
]


def run_all(application) -> list:
    return [check(application) for check in ALL_CHECKS]
