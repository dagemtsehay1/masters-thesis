"""Exact alias matching, then fuzzy matching, against a language's alias
table - the two tiers that should resolve most transcripts without ever
needing the Qwen fallback (Phase 6).

`rapidfuzz` (tiny, pure-C string distance) rather than an LLM: for a fixed
five-command vocabulary, deterministic fuzzy matching against near-miss ASR
output is both faster and more predictable than a sub-1B language model.
"""
from typing import Optional, Tuple

from rapidfuzz import fuzz, process

from src.intent.aliases import get_aliases


class RuleBasedParser:
    def __init__(self, language: str = "en", fuzzy_threshold: float = 80.0):
        self._fuzzy_threshold = fuzzy_threshold
        self._phrase_to_canonical = {}
        for canonical, phrases in get_aliases(language).items():
            for phrase in phrases:
                self._phrase_to_canonical[phrase] = canonical

    def parse(self, normalized_text: str) -> Tuple[Optional[str], float]:
        """Returns (canonical_command, confidence), or (None, 0.0)."""
        if not normalized_text or not self._phrase_to_canonical:
            return None, 0.0

        if normalized_text in self._phrase_to_canonical:
            return self._phrase_to_canonical[normalized_text], 0.95

        for phrase, canonical in self._phrase_to_canonical.items():
            if phrase in normalized_text:
                return canonical, 0.85

        match = process.extractOne(normalized_text, self._phrase_to_canonical.keys(), scorer=fuzz.WRatio)
        if match is not None:
            phrase, score, _ = match
            if score >= self._fuzzy_threshold:
                return self._phrase_to_canonical[phrase], score / 100.0

        return None, 0.0
