"""The canonical robot command object.

This is the only shape the robot layer is allowed to trust. Voice, gesture,
manual UI input, and (in later phases) Qwen must all produce one of these -
rather than a raw string - before anything reaches `RobotController`.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Action = Literal["move", "turn", "stop", "emergency_stop"]
Direction = Literal["forward", "backward", "left", "right", "around"]
Source = Literal["voice", "gesture", "manual", "emergency", "combined"]


class RobotCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Action
    direction: Optional[Direction] = None
    speed: Optional[float] = None
    duration: Optional[float] = None
    source: Source
    confidence: float = 1.0
    language: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, value))
