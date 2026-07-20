"""The canonical, language-independent command vocabulary.

Every language's alias table (src/speech/languages/*.py) maps its own
phrases to these same canonical names - this is what keeps the robot's
command set language-independent: English and Amharic both resolve to
"move_forward", "stop", etc., never to each other's words.

`CANONICAL_TO_LEGACY` bridges into the small shared vocabulary voice and
gesture have used since Phase 1-3 (`"go"`, `"left"`, ...) so the fusion
engine and RobotCommand adapter don't need to change shape - the alias/
fuzzy/Qwen resolution tiers all operate in terms of canonical names, and
only the final wire value handed to `FusionEngine` is the legacy word.
"""
from typing import Dict, List

from src.speech.languages import am, en

CANONICAL_COMMANDS = ["move_forward", "turn_left", "turn_right", "turn_around", "stop"]

CANONICAL_TO_LEGACY = {
    "move_forward": "go",
    "turn_left": "left",
    "turn_right": "right",
    "turn_around": "back",
    "stop": "stop",
}

_LANGUAGE_ALIASES = {
    "en": en.ALIASES,
    "am": am.ALIASES,
}


def get_aliases(language: str) -> Dict[str, List[str]]:
    return _LANGUAGE_ALIASES.get(language, {})
