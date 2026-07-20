"""The voice pipeline's output object, mirroring GestureEvent so the fusion
engine can treat both modalities symmetrically.

`IntentEngine.resolve()` (the terminal step of the Whisper -> normalize ->
alias/fuzzy/Qwen pipeline) produces one of these, carrying the resolved
legacy command word plus the detected language and a combined confidence.
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

VoiceCommand = Literal["go", "back", "stop", "left", "right"]


class VoiceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: Optional[VoiceCommand] = None
    confidence: float = 1.0
    language: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
