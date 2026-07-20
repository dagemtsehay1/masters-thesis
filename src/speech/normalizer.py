"""Per-language text normalization.

English normalization (punctuation/whitespace/case) is generic enough to
live here; Amharic needs script-specific handling (Ge'ez punctuation,
transliteration variants), which lives in `src/speech/languages/am.py`
and is dispatched to from here once a language is known.
"""
import re
import unicodedata

_PUNCTUATION_RE = re.compile(r"[.,!?;:\"'`~()\[\]{}]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str, language: str = "en") -> str:
    text = unicodedata.normalize("NFKC", text)

    if language == "am":
        from src.speech.languages.am import normalize_amharic

        text = normalize_amharic(text)
    else:
        text = text.strip().lower()
        text = _PUNCTUATION_RE.sub("", text)

    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()
