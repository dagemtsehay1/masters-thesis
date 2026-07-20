"""Strict schema for what qwen3:0.6b is allowed to return.

The model is prompted to emit exactly this JSON. Anything that doesn't
validate against it (extra fields, out-of-vocabulary action/direction,
malformed JSON) is rejected and treated as "unresolved" - the model never
gets a privileged path to the robot, it only ever proposes a candidate
that then goes through the same validator/safety chain as everything else.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict

# Canonical actions/directions the model may choose from, matching
# src/intent/aliases.py's canonical vocabulary (expressed here in the
# action+direction decomposition the model finds easiest to emit).
QWEN_ACTIONS = {"move", "turn", "stop"}
QWEN_DIRECTIONS = {"forward", "left", "right", "around", None}


class QwenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    direction: Optional[str] = None
    speed: Optional[float] = None
    duration: Optional[float] = None
    confidence: float = 0.0
    reason: str = ""


def to_canonical(response: QwenResponse) -> Optional[str]:
    """Maps a validated QwenResponse to a canonical command name, or None
    if the action/direction combination isn't one we recognize."""
    if response.action not in QWEN_ACTIONS or response.direction not in QWEN_DIRECTIONS:
        return None

    mapping = {
        ("move", "forward"): "move_forward",
        ("turn", "left"): "turn_left",
        ("turn", "right"): "turn_right",
        ("turn", "around"): "turn_around",
        ("stop", None): "stop",
    }
    return mapping.get((response.action, response.direction))
