"""Orchestrates the intent-resolution tiers: normalize -> exact/alias match
-> fuzzy match -> (optional) Qwen fallback -> confidence gate -> VoiceEvent.

This is the pipeline's single terminal-output point for voice: it always
returns either `None` (nothing resolved, or below threshold - rejected
rather than passed through) or a fully-formed `VoiceEvent`, never raw text.

It holds one rule parser per enabled language and dispatches on the
language Whisper detected for each utterance (or the pinned language when
detection is off), so the same engine handles English, Amharic, and the
mixed case where different utterances come in in different languages - all
resolving to the same language-independent canonical vocabulary.
"""
import logging
from typing import List, Optional

from src.intent.aliases import CANONICAL_TO_LEGACY
from src.intent.rule_parser import RuleBasedParser
from src.speech.normalizer import normalize_text
from src.voice.events import VoiceEvent

logger = logging.getLogger("intent.engine")


class IntentEngine:
    def __init__(
        self,
        language: str = "en",
        enabled_languages: Optional[List[str]] = None,
        confidence_threshold: float = 0.55,
        qwen_client=None,
    ):
        self._default_language = language
        languages = enabled_languages or [language]
        self._parsers = {lang: RuleBasedParser(language=lang) for lang in languages}
        self._threshold = confidence_threshold
        self._qwen_client = qwen_client  # None disables the fallback tier entirely

    def resolve(
        self, transcript: str, transcript_confidence: float = 1.0, language: Optional[str] = None
    ) -> Optional[VoiceEvent]:
        if not transcript:
            return None

        resolved_language = language if language in self._parsers else self._default_language
        parser = self._parsers.get(resolved_language) or next(iter(self._parsers.values()))

        normalized = normalize_text(transcript, language=resolved_language)

        canonical, rule_confidence = parser.parse(normalized)
        source_tier = "rule"

        if canonical is None and self._qwen_client is not None and self._qwen_client.enabled:
            canonical, rule_confidence = self._qwen_client.resolve(normalized, language=resolved_language)
            source_tier = "qwen"

        if canonical is None:
            logger.info("No intent resolved for transcript '%s' (language=%s)", transcript, resolved_language)
            return None

        combined_confidence = min(transcript_confidence, rule_confidence)
        if combined_confidence < self._threshold:
            logger.info(
                "Resolved '%s' (%s tier) but confidence %.2f is below threshold %.2f - rejecting",
                canonical,
                source_tier,
                combined_confidence,
                self._threshold,
            )
            return None

        legacy_word = CANONICAL_TO_LEGACY.get(canonical)
        if legacy_word is None:
            return None

        return VoiceEvent(command=legacy_word, confidence=combined_confidence, language=resolved_language)
