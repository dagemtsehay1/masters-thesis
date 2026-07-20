"""UI-facing state snapshots.

The UI never reads Application/service internals directly and components
never modify each other directly - `ServiceWorker` (workers.py) emits these
as immutable snapshots over Qt signals, and panels only ever render what
they're given. This is the "one central application-state model as the
source of truth" the plan calls for, kept intentionally small: one model
per panel's concern rather than a single monolithic blob.
"""
from datetime import datetime, timezone
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ComponentState = Literal["ready", "starting", "active", "disabled", "degraded", "error", "disconnected"]


class ComponentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    state: ComponentState
    message: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VoiceUIState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listening: bool = False
    speech_detected: bool = False
    language: Optional[str] = None
    transcript: str = ""
    normalized_text: str = ""
    confidence: float = 0.0
    processing_state: Literal["idle", "listening", "processing", "complete", "error"] = "idle"


class GestureUIState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera_active: bool = False
    hand_detected: bool = False
    handedness: Optional[str] = None
    gesture: Optional[str] = None
    confidence: float = 0.0
    state: Literal["idle", "candidate", "confirmed", "cooldown"] = "idle"
    confirmation_progress: int = 0
    confirmation_required: int = 1


class CommandUIState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Optional[str] = None
    action: Optional[str] = None
    direction: Optional[str] = None
    confidence: float = 0.0
    status: Literal["none", "validated", "rejected"] = "none"
    rejection_reason: Optional[str] = None


class AppState(BaseModel):
    """One full snapshot of everything the UI might want to show at once -
    emitted by ServiceWorker after each loop tick."""

    model_config = ConfigDict(extra="forbid")

    components: Dict[str, ComponentStatus] = {}
    voice: VoiceUIState = VoiceUIState()
    gesture: GestureUIState = GestureUIState()
    command: CommandUIState = CommandUIState()
    emergency_stop_active: bool = False
    fusion_mode: str = ""
    last_robot_command: Optional[str] = None
    robot_state: str = "idle"
    robot_mode: str = "stop"
