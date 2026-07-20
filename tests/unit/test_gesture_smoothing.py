import time

from src.gesture.smoothing import GestureSmoother


def test_single_frame_does_not_confirm():
    smoother = GestureSmoother(confirmation_frames=5, cooldown_s=1.0)
    event = smoother.update("go", 0.9)
    assert event.state == "candidate"
    assert event.gesture == "go"


def test_confirms_after_required_consecutive_frames():
    smoother = GestureSmoother(confirmation_frames=3, cooldown_s=1.0)
    assert smoother.update("go", 0.9).state == "candidate"
    assert smoother.update("go", 0.9).state == "candidate"
    confirmed = smoother.update("go", 0.9)
    assert confirmed.state == "confirmed"
    assert confirmed.gesture == "go"


def test_changing_gesture_mid_confirmation_restarts_the_count():
    smoother = GestureSmoother(confirmation_frames=3, cooldown_s=1.0)
    smoother.update("go", 0.9)
    smoother.update("go", 0.9)
    # Switches to a different pose right before it would have confirmed.
    switched = smoother.update("stop", 0.9)
    assert switched.state == "candidate"
    assert switched.gesture == "stop"
    assert smoother.confirmation_progress == 1


def test_no_pose_resets_to_idle():
    smoother = GestureSmoother(confirmation_frames=3, cooldown_s=1.0)
    smoother.update("go", 0.9)
    idle_event = smoother.update(None, 0.0)
    assert idle_event.state == "idle"
    assert idle_event.gesture is None


def test_cooldown_suppresses_immediate_reconfirmation():
    smoother = GestureSmoother(confirmation_frames=1, cooldown_s=0.2)
    confirmed = smoother.update("go", 0.9)
    assert confirmed.state == "confirmed"

    # Still within the cooldown window - must not confirm again yet.
    during_cooldown = smoother.update("go", 0.9)
    assert during_cooldown.state == "cooldown"


def test_holding_the_pose_reconfirms_after_cooldown_elapses():
    smoother = GestureSmoother(confirmation_frames=1, cooldown_s=0.05)
    first = smoother.update("go", 0.9)
    assert first.state == "confirmed"

    time.sleep(0.08)
    second = smoother.update("go", 0.9)
    assert second.state == "confirmed"


def test_releasing_during_cooldown_returns_to_idle_after_it_elapses():
    smoother = GestureSmoother(confirmation_frames=1, cooldown_s=0.05)
    smoother.update("go", 0.9)

    time.sleep(0.08)
    released = smoother.update(None, 0.0)
    assert released.state == "idle"
