"""The gesture pipeline's output object.

Replaces the old `GestureDetector.detect()` -> `(command, frame)` tuple.
`gesture` uses the same small legacy vocabulary voice commands still use
(`"go"`, `"back"`, `"stop"`, `"left"`, `"right"`) so both modalities can be
fused with the same command value until Phase 5 introduces a proper
intent layer for both.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

GestureName = Literal["go", "back", "stop", "left", "right"]
GestureState = Literal["idle", "candidate", "confirmed", "cooldown"]
Handedness = Literal["Left", "Right"]


class GestureEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gesture: Optional[GestureName] = None
    confidence: float = 0.0
    hand: Optional[Handedness] = None
    state: GestureState = "idle"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
