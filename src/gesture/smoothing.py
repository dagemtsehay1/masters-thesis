"""Temporal confirmation for classified gestures.

This is the fix for the single most important gap in the original
pipeline: a bare classification was trusted the instant it appeared, so
one unstable frame could trigger a command. `GestureSmoother` requires
`confirmation_frames` consecutive matching classifications before a
gesture is reported as confirmed, then enforces a cooldown before the same
gesture can confirm again - while still allowing a *held* pose to
re-confirm after the cooldown, which is what lets "hold the forward pose"
keep producing fresh commands (and keep the dead-man timeout satisfied).

State machine per call to `update()`:
    idle      -> candidate  (a recognized pose appears)
    candidate -> candidate  (same pose, count < confirmation_frames)
    candidate -> confirmed  (same pose, count reaches confirmation_frames)
    confirmed -> cooldown   (always, the tick right after confirming)
    cooldown  -> candidate  (cooldown elapsed, same pose still held)
    cooldown  -> idle       (cooldown elapsed, pose released/changed)
    any       -> idle       (no recognized pose this tick)
"""
import time
from typing import Optional

from src.gesture.events import GestureEvent


class GestureSmoother:
    def __init__(self, confirmation_frames: int = 5, cooldown_s: float = 0.8):
        self._confirmation_frames = max(1, confirmation_frames)
        self._cooldown_s = cooldown_s

        self._state = "idle"
        self._candidate_gesture: Optional[str] = None
        self._candidate_count = 0
        self._last_confirmed_gesture: Optional[str] = None
        self._cooldown_until = 0.0

    def update(
        self, gesture: Optional[str], confidence: float, hand: Optional[str] = None
    ) -> GestureEvent:
        now = time.monotonic()

        if self._state == "cooldown":
            if now < self._cooldown_until:
                return GestureEvent(
                    gesture=self._last_confirmed_gesture, confidence=confidence, hand=hand, state="cooldown"
                )
            # Cooldown elapsed - decide whether to resume confirming (held pose) or go idle.
            self._state = "idle"

        if gesture is None:
            self._state = "idle"
            self._candidate_gesture = None
            self._candidate_count = 0
            return GestureEvent(gesture=None, confidence=0.0, hand=hand, state="idle")

        if gesture != self._candidate_gesture:
            self._candidate_gesture = gesture
            self._candidate_count = 1
        else:
            self._candidate_count += 1

        if self._candidate_count >= self._confirmation_frames:
            self._state = "cooldown"
            self._cooldown_until = now + self._cooldown_s
            self._last_confirmed_gesture = gesture
            confirmed_event = GestureEvent(gesture=gesture, confidence=confidence, hand=hand, state="confirmed")
            self._candidate_count = 0
            return confirmed_event

        self._state = "candidate"
        return GestureEvent(gesture=gesture, confidence=confidence, hand=hand, state="candidate")

    @property
    def confirmation_progress(self) -> int:
        return self._candidate_count

    @property
    def confirmation_required(self) -> int:
        return self._confirmation_frames

    # ================= RUNTIME CONFIGURATION =================
    # Lets the Configuration panel adjust gesture-confirmation settings
    # (main.txt's "gesture-confirmation settings") without restarting the
    # gesture pipeline. Mid-confirmation state is intentionally left alone -
    # only the thresholds used by the *next* evaluation change.

    def set_confirmation_frames(self, frames: int) -> None:
        self._confirmation_frames = max(1, int(frames))

    def set_cooldown_s(self, cooldown_s: float) -> None:
        self._cooldown_s = max(0.0, float(cooldown_s))
