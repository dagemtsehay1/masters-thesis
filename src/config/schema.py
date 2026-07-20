"""Typed configuration schema for the application.

Every setting the app can be tuned with lives here as a pydantic model, so
config/presets/*.yaml is validated against a real schema instead of being
trusted blindly. `extra="forbid"` on every section means a typo in a preset
file (or a stale field from a removed feature) fails loudly at startup
instead of being silently ignored.

Not every field below is wired into a running component - `camera.resolution`
and `camera.preview_fps` are accepted but not yet enforced anywhere (no
component resizes the capture or throttles the UI preview independently of
inference rate), kept only so the preset file format doesn't need to change
shape again once something does enforce them.
"""
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneralConfig(_StrictModel):
    app_mode: Literal["gui", "headless"] = "gui"
    debug: bool = False
    active_preset: Optional[str] = None  # set by the loader, purely informational (e.g. for the UI header)


class LoggingConfig(_StrictModel):
    level: str = "INFO"
    log_to_file: bool = False
    file_path: Optional[str] = None


class CameraConfig(_StrictModel):
    device_index: int = 0
    resolution: Tuple[int, int] = (640, 480)  # not yet enforced anywhere
    preview_fps: int = 30  # not yet enforced anywhere (UI renders whatever frame arrives)


class GestureConfig(_StrictModel):
    enabled: bool = True
    min_hand_detection_confidence: float = 0.6
    min_tracking_confidence: float = 0.6
    model_asset_path: str = "model/hand_landmarker.task"
    confirmation_frames: int = 5  # consecutive matching frames required before a gesture is confirmed
    cooldown_ms: int = 800  # minimum time between two confirmations of the same gesture
    inference_fps: Optional[int] = 15  # None = run inference as fast as frames arrive
    show_landmarks: bool = True  # debug overlay on the preview frame; can be disabled to save CPU


class MicrophoneConfig(_StrictModel):
    device_index: Optional[int] = None
    sample_rate: int = 16000


class VoiceConfig(_StrictModel):
    enabled: bool = True


class WhisperConfig(_StrictModel):
    model: str = "small"  # faster-whisper model size/name - multilingual (never "*.en") since Amharic is required
    device: Literal["cpu", "cuda"] = "cpu"
    compute_type: str = "int8"  # int8 on CPU, float16 selectable if a GPU is available


class VADConfig(_StrictModel):
    backend: Literal["webrtcvad", "energy"] = "webrtcvad"
    aggressiveness: int = 2  # webrtcvad's 0 (least aggressive) - 3 (most aggressive) filtering
    frame_ms: Literal[10, 20, 30] = 20
    silence_timeout_s: float = 0.6
    max_recording_s: float = 8.0


class LanguagesConfig(_StrictModel):
    enabled: List[str] = ["en"]
    mode: Literal["auto", "en", "am"] = "auto"
    default_language: str = "en"


class SpeechConfig(_StrictModel):
    whisper: WhisperConfig = WhisperConfig()
    vad: VADConfig = VADConfig()
    languages: LanguagesConfig = LanguagesConfig()
    confidence_threshold: float = 0.55


class QwenConfig(_StrictModel):
    """Optional local LLM intent fallback via Ollama. Disabled by default:
    qwen3:0.6b is only a last-resort tier for transcripts the deterministic
    alias/fuzzy matcher can't resolve, and its reliability at that size is
    genuinely uncertain (see docs) - so it's opt-in, never load-bearing."""

    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "qwen3:0.6b"
    timeout_s: float = 3.0
    retries: int = 1
    temperature: float = 0.0  # deterministic
    max_tokens: int = 64
    languages: List[str] = ["en"]  # Amharic is routed through aliases only in the first iteration


class IntentConfig(_StrictModel):
    qwen: QwenConfig = QwenConfig()


FusionMode = Literal[
    "voice_only",
    "gesture_only",
    "either",
    "voice_priority",
    "gesture_priority",
    "latest_wins",
    "highest_confidence",
    "confirmation",
    "combined",
]

ConflictPolicy = Literal["highest_confidence", "voice_wins", "gesture_wins"]


class MinimumConfidenceConfig(_StrictModel):
    voice: float = 0.70
    gesture: float = 0.80


class FusionPriorityConfig(_StrictModel):
    """Tie-break ranking used when a category needs to unconditionally
    outrank another regardless of the active `mode` - e.g. "stop" outranks
    a normal move/turn command from either modality no matter which fusion
    mode is selected. `voice`/`gesture` here are only used as the last-resort
    tiebreak inside modes that don't already have their own rule for it."""

    emergency_stop: int = 100
    stop: int = 90
    gesture: int = 60
    voice: int = 50


class FusionConfig(_StrictModel):
    mode: FusionMode = "voice_priority"
    event_window_ms: int = 1500
    conflict_policy: ConflictPolicy = "highest_confidence"
    minimum_confidence: MinimumConfidenceConfig = MinimumConfidenceConfig()
    priority: FusionPriorityConfig = FusionPriorityConfig()
    require_confirmation_for: List[str] = []
    duplicate_command_cooldown_ms: int = 1200
    stale_event_timeout_ms: int = 2000


class RobotConfig(_StrictModel):
    linear_speed: float = 2.0
    angular_speed: float = 2.0
    max_linear_speed: float = 3.0
    max_angular_speed: float = 3.0
    max_command_duration_s: Optional[float] = None
    rotation_tolerance_deg: float = 3.0


class SafetyConfig(_StrictModel):
    dead_man_timeout_s: float = 3.0
    allowed_actions: List[str] = ["move", "turn", "stop", "emergency_stop"]


class CoppeliaConfig(_StrictModel):
    host: str = "localhost"
    port: int = 23000
    robot_object: str = "/youBot"
    connect_retry_attempts: int = 3
    connect_retry_delay_s: float = 1.0


class UIConfig(_StrictModel):
    window_title: str = "Robot Controller"
    metrics_refresh_ms: int = 1000
    maximum_visible_logs: int = 1000
    chart_history_samples: int = 120
    show_performance_monitor: bool = True
    confirm_before_exit: bool = True


class PrivacyConfig(_StrictModel):
    store_transcripts: bool = False


class AppConfig(_StrictModel):
    general: GeneralConfig = GeneralConfig()
    logging: LoggingConfig = LoggingConfig()
    camera: CameraConfig = CameraConfig()
    gesture: GestureConfig = GestureConfig()
    microphone: MicrophoneConfig = MicrophoneConfig()
    voice: VoiceConfig = VoiceConfig()
    speech: SpeechConfig = SpeechConfig()
    intent: IntentConfig = IntentConfig()
    fusion: FusionConfig = FusionConfig()
    robot: RobotConfig = RobotConfig()
    safety: SafetyConfig = SafetyConfig()
    coppelia: CoppeliaConfig = CoppeliaConfig()
    ui: UIConfig = UIConfig()
    privacy: PrivacyConfig = PrivacyConfig()
