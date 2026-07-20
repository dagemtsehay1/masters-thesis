"""The canonical command whitelist.

Enumerates every (action, direction) pair the robot is allowed to execute.
Anything not listed here is rejected by the validator before it ever
reaches `RobotController` - this is what keeps a bug or a misclassified
gesture/transcript from turning into an arbitrary robot action.
"""
from typing import Dict, Optional, Set

ALLOWED_ACTIONS: Dict[str, Set[Optional[str]]] = {
    "move": {"forward"},  # "backward" is reserved: no detector produces it yet
    "turn": {"left", "right", "around"},
    "stop": {None},
    "emergency_stop": {None},
}


def is_allowed(action: str, direction: Optional[str]) -> bool:
    directions = ALLOWED_ACTIONS.get(action)
    if directions is None:
        return False
    return direction in directions
