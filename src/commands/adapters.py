"""Temporary adapter translating legacy string commands into RobotCommand.

The voice and gesture detectors still emit plain strings (they gain proper
VoiceEvent/GestureEvent objects in Phases 5 and 2 respectively). Until then,
this is the *single* translation point both entrypoints use, so the
string-to-canonical-command mapping is defined exactly once instead of
being duplicated in main.py and gui_main.py.
"""
from typing import Optional

from src.commands.schema import RobotCommand, Source

_LEGACY_COMMAND_MAP = {
    "go": ("move", "forward"),
    "back": ("turn", "around"),
    "left": ("turn", "left"),
    "right": ("turn", "right"),
    "stop": ("stop", None),
}


def command_from_legacy_string(
    text: str, source: Source, confidence: float = 1.0
) -> Optional[RobotCommand]:
    """Returns None if `text` isn't a recognized legacy command word."""
    mapping = _LEGACY_COMMAND_MAP.get(text)
    if mapping is None:
        return None
    action, direction = mapping
    return RobotCommand(action=action, direction=direction, source=source, confidence=confidence)
