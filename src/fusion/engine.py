"""The single fusion implementation.

Replaces the two separate, divergent arbitration algorithms that used to
live in `main.py` (a priority `if/elif`) and `gui_main.py`
(`resolve_final_command`/`get_active_command_score`) - both entrypoints now
call into this one engine instead.
"""
import logging
import time
from dataclasses import dataclass
from typing import Optional

from src.commands.adapters import command_from_legacy_string
from src.commands.schema import RobotCommand
from src.config.schema import FusionConfig
from src.fusion.modes import MODE_FUNCTIONS
from src.fusion.policy import (
    NormalizedEvent,
    filter_min_confidence,
    filter_stale,
    is_duplicate,
    normalize_gesture_event,
    normalize_voice_event,
)

logger = logging.getLogger("fusion.engine")

# Which canonical command categories a resolved command belongs to, for
# `fusion.require_confirmation_for`. "high_speed" has no predicate today -
# nothing in the legacy vocabulary carries a variable speed yet - so it's
# accepted as a valid category but never actually matches, which is the
# correct behavior for a not-yet-applicable forward-compatible setting.
_CONFIRMATION_CATEGORIES = {
    "continuous_motion": lambda command: command.action == "move",
}


@dataclass
class FusionDecision:
    command: RobotCommand
    reason: str


class FusionEngine:
    def __init__(self, config: FusionConfig):
        self.config = config
        self._last_value: Optional[str] = None
        self._last_time: float = 0.0

    def resolve(self, voice_event=None, gesture_event=None, now: Optional[float] = None) -> Optional[FusionDecision]:
        now = now if now is not None else time.time()
        cfg = self.config

        voice = normalize_voice_event(voice_event, now)
        gesture = normalize_gesture_event(gesture_event, now)

        max_age_s = cfg.stale_event_timeout_ms / 1000.0
        voice = filter_stale(voice, max_age_s)
        gesture = filter_stale(gesture, max_age_s)

        voice = filter_min_confidence(voice, cfg.minimum_confidence.voice)
        gesture = filter_min_confidence(gesture, cfg.minimum_confidence.gesture)

        if voice is None and gesture is None:
            return None

        stop_decision = self._resolve_stop_override(voice, gesture, now)
        if stop_decision is not None:
            return stop_decision

        mode_fn = MODE_FUNCTIONS.get(cfg.mode)
        if mode_fn is None:
            logger.warning("Unknown fusion mode '%s', falling back to voice_priority", cfg.mode)
            mode_fn = MODE_FUNCTIONS["voice_priority"]

        resolution = mode_fn(voice, gesture)
        if resolution is None:
            return None

        value, source, confidence = resolution

        candidate = command_from_legacy_string(value, source=source, confidence=confidence)
        if candidate is None:
            return None

        if self._requires_confirmation(candidate) and not self._modalities_agree(voice, gesture, value):
            logger.info("'%s' requires cross-modal confirmation and didn't get it this tick", value)
            return None

        return self._finalize(value, source, confidence, now, reason=f"mode={cfg.mode}")

    # ================= HELPERS =================

    def _resolve_stop_override(
        self, voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent], now: float
    ) -> Optional[FusionDecision]:
        """"stop" outranks any normal move/turn command from either
        modality regardless of the active mode - matches
        priority.stop sitting above priority.voice/priority.gesture."""
        voice_stops = voice is not None and voice.value == "stop"
        gesture_stops = gesture is not None and gesture.value == "stop"

        if voice_stops and gesture_stops:
            confidence = max(voice.confidence, gesture.confidence)
            return self._finalize("stop", "combined", confidence, now, reason="stop (both modalities)")
        if voice_stops:
            return self._finalize("stop", "voice", voice.confidence, now, reason="stop overrides fusion")
        if gesture_stops:
            return self._finalize("stop", "gesture", gesture.confidence, now, reason="stop overrides fusion")
        return None

    def _requires_confirmation(self, command: RobotCommand) -> bool:
        for category in self.config.require_confirmation_for:
            predicate = _CONFIRMATION_CATEGORIES.get(category)
            if predicate and predicate(command):
                return True
        return False

    @staticmethod
    def _modalities_agree(
        voice: Optional[NormalizedEvent], gesture: Optional[NormalizedEvent], value: str
    ) -> bool:
        return bool(voice and gesture and voice.value == value and gesture.value == value)

    def _finalize(
        self, value: str, source: str, confidence: float, now: float, reason: str
    ) -> Optional[FusionDecision]:
        cooldown_s = self.config.duplicate_command_cooldown_ms / 1000.0
        if is_duplicate(value, self._last_value, self._last_time, now, cooldown_s):
            return None

        command = command_from_legacy_string(value, source=source, confidence=confidence)
        if command is None:
            return None

        self._last_value = value
        self._last_time = now
        return FusionDecision(command=command, reason=reason)
