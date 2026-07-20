"""Amharic normalization and alias table.

IMPORTANT (see docs/amharic_dataset_protocol.md): the phrases below are a
*starting* table of the standard imperative forms for each command. For
thesis-grade results they must be validated/extended against a small, real,
recorded set of how the actual Whisper model transcribes these commands
from real speakers on the target hardware - Whisper's Amharic transcription
is a low-resource case and its real output often differs from textbook
orthography (spacing, gemination, vowel choices). Treat this table as the
seed the recording protocol refines, not a validated ground truth.

Latin transliterations are included as an explicitly lower-confidence
secondary tier for users who speak the command but whose transcription (or
typing) comes out romanized rather than in Ge'ez script.
"""
import re

# Ethiopic punctuation marks: word-space (፣), comma-equivalent (፤),
# semicolon-equivalent (፥), colon-equivalent (፦), preface-colon (፧),
# paragraph separator (፨), full stop (።).
_GEEZ_PUNCTUATION_RE = re.compile(r"[፣፤፥፦፧፨።]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_amharic(text: str) -> str:
    text = text.strip()
    text = _GEEZ_PUNCTUATION_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


# Canonical command -> Amharic phrases (Ge'ez script) + practical Latin
# transliterations. Mapped to the same canonical names as the English table
# so the robot's command vocabulary stays language-independent.
ALIASES = {
    "move_forward": [
        "ወደፊት ሂድ",
        "ወደ ፊት ተንቀሳቀስ",
        "ቀጥል",
        # transliterations
        "wede fit hid",
        "wede fit",
    ],
    "turn_left": [
        "ወደ ግራ ታጠፍ",
        "ግራ",
        "wede gra tatef",
        "gra",
    ],
    "turn_right": [
        "ወደ ቀኝ ታጠፍ",
        "ቀኝ",
        "wede kegn tatef",
        "kegn",
    ],
    "turn_around": [
        "ወደ ኋላ ተመለስ",
        "ተመለስ",
        "wede hwala temeles",
        "temeles",
    ],
    "stop": [
        "ቁም",
        "አቁም",
        "ተወ",
        "kum",
        "akum",
    ],
}
