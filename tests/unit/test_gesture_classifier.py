from types import SimpleNamespace

from src.gesture.classifier import GestureClassifier


def _landmark(x, y, z=0.0):
    return SimpleNamespace(x=x, y=y, z=z)


def _hand(finger_states, wrist=(0.5, 0.5), hand_length=0.2):
    """Builds 21 synthetic landmarks for one hand, upright (wrist below
    middle MCP, matching the classifier's own hand-local "up" axis when the
    hand isn't rotated). finger_states maps finger -> "up"/"down"."""
    wx, wy = wrist
    landmarks = [None] * 21
    landmarks[0] = _landmark(wx, wy)
    landmarks[9] = _landmark(wx, wy - hand_length)  # middle MCP defines the "up" axis

    tips = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
    pips = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

    pip_y = wy - hand_length * 0.6
    for finger, tip_idx in tips.items():
        pip_idx = pips[finger]
        landmarks[pip_idx] = _landmark(wx, pip_y)

        if finger_states.get(finger, "down") == "up":
            landmarks[tip_idx] = _landmark(wx, pip_y - hand_length * 0.6)
        else:
            landmarks[tip_idx] = _landmark(wx, pip_y + hand_length * 0.2)

    landmarks[4] = _landmark(wx - 0.05, wy)  # thumb tip, unused by the classifier
    return landmarks


def _pointing_hand(direction, wrist=(0.5, 0.5), hand_length=0.2):
    """A hand with only the index finger extended, laterally offset enough
    that the classifier's dx-dominance test for "pointing" fires."""
    wx, wy = wrist
    landmarks = [None] * 21
    landmarks[0] = _landmark(wx, wy)
    landmarks[9] = _landmark(wx, wy - hand_length)

    sign = 1.0 if direction == "right" else -1.0
    pip_y = wy - hand_length * 0.6
    landmarks[6] = _landmark(wx, pip_y)
    landmarks[8] = _landmark(wx + sign * 1.5 * hand_length, wy - hand_length * 0.8)

    for tip_idx, pip_idx in ((12, 10), (16, 14), (20, 18)):
        landmarks[pip_idx] = _landmark(wx, pip_y)
        landmarks[tip_idx] = _landmark(wx, pip_y + hand_length * 0.2)

    return landmarks


def test_four_fingers_up_is_stop():
    landmarks = _hand({"index": "up", "middle": "up", "ring": "up", "pinky": "up"})
    gesture, confidence = GestureClassifier().classify(landmarks)
    assert gesture == "stop"
    assert confidence > 0.0


def test_index_pointing_right_is_right():
    gesture, _ = GestureClassifier().classify(_pointing_hand("right"))
    assert gesture == "right"


def test_index_pointing_left_is_left():
    gesture, _ = GestureClassifier().classify(_pointing_hand("left"))
    assert gesture == "left"


def test_three_fingers_up_raised_above_wrist_is_go():
    landmarks = _hand({"index": "up", "middle": "up", "ring": "up", "pinky": "down"})
    gesture, _ = GestureClassifier().classify(landmarks)
    assert gesture == "go"


def test_three_fingers_up_lowered_below_wrist_is_back():
    # A negative hand_length flips the hand's own "up" axis to point
    # downward in the image (hand held upside-down, fingers extended away
    # from the wrist toward the bottom of the frame) - the mirror image of
    # the "go" pose, and what the classifier's avg-tip-y-vs-wrist check for
    # "back" is actually looking for.
    landmarks = _hand(
        {"index": "up", "middle": "up", "ring": "up", "pinky": "down"},
        hand_length=-0.2,
    )
    gesture, _ = GestureClassifier().classify(landmarks)
    assert gesture == "back"


def test_all_fingers_down_is_no_gesture():
    landmarks = _hand({"index": "down", "middle": "down", "ring": "down", "pinky": "down"})
    gesture, confidence = GestureClassifier().classify(landmarks)
    assert gesture is None
    assert confidence == 0.0
