"""Shared filtering/comparison helpers used by the fusion engine.

Kept separate from engine.py so the staleness/confidence/duplicate rules -
each independently meaningful per the improvement plan's "define clear
behavior for low-confidence, stale, and repeated commands" requirement -
can be tested in isolation from the mode-dispatch logic.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class NormalizedEvent:
    value: str
    confidence: float
    age_s: float
    source: str  # "voice" | "gesture"


def normalize_voice_event(event, now: float) -> Optional[NormalizedEvent]:
    if event is None or event.command is None:
        return None
    age = max(0.0, now - event.timestamp.timestamp())
    return NormalizedEvent(value=event.command, confidence=event.confidence, age_s=age, source="voice")


def normalize_gesture_event(event, now: float) -> Optional[NormalizedEvent]:
    if event is None or event.gesture is None or event.state != "confirmed":
        return None
    age = max(0.0, now - event.timestamp.timestamp())
    return NormalizedEvent(value=event.gesture, confidence=event.confidence, age_s=age, source="gesture")


def filter_stale(event: Optional[NormalizedEvent], max_age_s: float) -> Optional[NormalizedEvent]:
    if event is None:
        return None
    return event if event.age_s <= max_age_s else None


def filter_min_confidence(event: Optional[NormalizedEvent], threshold: float) -> Optional[NormalizedEvent]:
    if event is None:
        return None
    return event if event.confidence >= threshold else None


def is_duplicate(value: str, last_value: Optional[str], last_time: float, now: float, cooldown_s: float) -> bool:
    if last_value is None:
        return False
    return value == last_value and (now - last_time) < cooldown_s
