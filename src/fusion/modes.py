"""One function per fusion mode.

Each takes the already-filtered (staleness/min-confidence) normalized
voice/gesture candidates and returns a `(value, source, confidence)`
resolution, or None if this mode can't resolve a command from what's
available this tick. `engine.py` handles the parts that apply regardless
of mode (the "stop" override, duplicate suppression).
"""
from typing import Callable, Dict, Optional, Tuple

from src.fusion.policy import NormalizedEvent

Resolution = Optional[Tuple[str, str, float]]

_MOVE_HINT = "go"
_TURNS = {"left", "right"}


def _as_resolution(event: Optional[NormalizedEvent]) -> Resolution:
    return (event.value, event.source, event.confidence) if event else None


def voice_only(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    return _as_resolution(voice)


def gesture_only(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    return _as_resolution(gesture)


def either(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    if voice and gesture:
        return highest_confidence(voice, gesture)
    return _as_resolution(voice or gesture)


def voice_priority(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    return _as_resolution(voice or gesture)


def gesture_priority(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    return _as_resolution(gesture or voice)


def latest_wins(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    if voice and gesture:
        return _as_resolution(voice if voice.age_s <= gesture.age_s else gesture)
    return _as_resolution(voice or gesture)


def highest_confidence(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    if voice and gesture:
        return _as_resolution(voice if voice.confidence >= gesture.confidence else gesture)
    return _as_resolution(voice or gesture)


def confirmation(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    """Requires both modalities present and in agreement - "one modality
    confirms another". A single modality alone is not enough corroboration."""
    if not (voice and gesture):
        return None
    if voice.value != gesture.value:
        return None
    return voice.value, "combined", max(voice.confidence, gesture.confidence)


def combined(voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent]) -> Resolution:
    """Voice supplies the action, gesture supplies the direction/parameter.

    The current legacy vocabulary bundles action+direction into one word
    per modality rather than exposing them separately, so this is scoped to
    the one combination that vocabulary can actually express: an unspecific
    "go" from one modality paired with a specific turn direction from the
    other. Full action/direction composition arrives with Phase 5's
    decomposed intent objects.
    """
    if not (voice and gesture):
        return None
    if voice.value == gesture.value:
        return voice.value, "combined", max(voice.confidence, gesture.confidence)
    if voice.value == _MOVE_HINT and gesture.value in _TURNS:
        return gesture.value, "combined", min(voice.confidence, gesture.confidence)
    if gesture.value == _MOVE_HINT and voice.value in _TURNS:
        return voice.value, "combined", min(voice.confidence, gesture.confidence)
    return None


MODE_FUNCTIONS: Dict[str, Callable[[Optional[NormalizedEvent], Optional[NormalizedEvent]], Resolution]] = {
    "voice_only": voice_only,
    "gesture_only": gesture_only,
    "either": either,
    "voice_priority": voice_priority,
    "gesture_priority": gesture_priority,
    "latest_wins": latest_wins,
    "highest_confidence": highest_confidence,
    "confirmation": confirmation,
    "combined": combined,
}
