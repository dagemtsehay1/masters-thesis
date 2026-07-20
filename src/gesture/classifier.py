"""Rule-based gesture classification on normalized hand landmarks.

Generalizes the original detector's raw-pixel finger-up/dx-threshold rules
into a small hand-local coordinate frame, so classification degrades more
gracefully as the hand moves closer/further from the camera (scale
invariance) or tilts in the image plane (in-plane rotation invariance).

This intentionally stays rule-based rather than a trained model - see the
implementation plan's assessment: a fixed 5-gesture vocabulary is well
within reach of geometric rules once normalized, and a trained classifier's
data-collection/training cost isn't justified until measurement shows this
plateauing below an acceptable accuracy. Out-of-plane rotation (e.g. the
hand's back facing the camera at an angle) is a known, undealt-with
limitation of using 2D landmark coordinates for the local frame.

Landmark indices follow MediaPipe's hand landmark model:
  0 = wrist, 5/9/13/17 = index/middle/ring/pinky MCP,
  6/10/14/18 = index/middle/ring/pinky PIP, 8/12/16/20 = their tips.
"""
from typing import List, Optional, Tuple

import numpy as np

_WRIST = 0
_MIDDLE_MCP = 9
_TIPS = {"index": 8, "middle": 12, "ring": 16, "pinky": 20}
_PIPS = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

_FINGER_UP_MARGIN = 0.15  # tip must clear the pip by this many hand-lengths
_POINT_DX_THRESHOLD = 1.0  # lateral offset (in hand-lengths) to call it "pointing"
_RAISED_LOWERED_MARGIN = 0.12  # image-space margin for the raised/lowered "go"/"back" cue


def _hand_frame(landmarks) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    wrist = np.array([landmarks[_WRIST].x, landmarks[_WRIST].y])
    middle_mcp = np.array([landmarks[_MIDDLE_MCP].x, landmarks[_MIDDLE_MCP].y])

    up = middle_mcp - wrist
    scale = float(np.linalg.norm(up)) or 1e-6
    up_hat = up / scale
    right_hat = np.array([-up_hat[1], up_hat[0]])
    return wrist, up_hat, right_hat, scale


def _to_local(point, wrist, up_hat, right_hat, scale) -> np.ndarray:
    v = np.array([point.x, point.y]) - wrist
    return np.array([np.dot(v, right_hat), np.dot(v, up_hat)]) / scale


class GestureClassifier:
    def classify(self, landmarks: List) -> Tuple[Optional[str], float]:
        """Returns (gesture_name, confidence). gesture_name is None (with
        confidence 0.0) when no known pose is recognized."""
        wrist, up_hat, right_hat, scale = _hand_frame(landmarks)

        local = {}
        for finger in _TIPS:
            local[f"{finger}_tip"] = _to_local(landmarks[_TIPS[finger]], wrist, up_hat, right_hat, scale)
            local[f"{finger}_pip"] = _to_local(landmarks[_PIPS[finger]], wrist, up_hat, right_hat, scale)

        finger_margins = {
            finger: local[f"{finger}_tip"][1] - local[f"{finger}_pip"][1] for finger in _TIPS
        }
        fingers_up = {finger: margin > _FINGER_UP_MARGIN for finger, margin in finger_margins.items()}
        up_count = sum(fingers_up.values())

        if up_count == 4:
            confidence = self._margin_confidence(min(finger_margins.values()), _FINGER_UP_MARGIN)
            return "stop", confidence

        if fingers_up["index"] and not any(
            fingers_up[f] for f in ("middle", "ring", "pinky")
        ):
            index_local = local["index_tip"]
            if abs(index_local[0]) > abs(index_local[1]) and abs(index_local[0]) > _POINT_DX_THRESHOLD:
                direction = "right" if index_local[0] > 0 else "left"
                confidence = self._margin_confidence(abs(index_local[0]), _POINT_DX_THRESHOLD)
                return direction, confidence

        if up_count >= 3:
            avg_tip_y_image = np.mean(
                [landmarks[_TIPS[f]].y for f in _TIPS if fingers_up[f]]
            )
            wrist_y_image = landmarks[_WRIST].y

            if avg_tip_y_image < wrist_y_image - _RAISED_LOWERED_MARGIN:
                confidence = self._margin_confidence(
                    wrist_y_image - _RAISED_LOWERED_MARGIN - avg_tip_y_image, _RAISED_LOWERED_MARGIN
                )
                return "go", confidence

            if avg_tip_y_image > wrist_y_image + _RAISED_LOWERED_MARGIN:
                confidence = self._margin_confidence(
                    avg_tip_y_image - wrist_y_image - _RAISED_LOWERED_MARGIN, _RAISED_LOWERED_MARGIN
                )
                return "back", confidence

        return None, 0.0

    @staticmethod
    def _margin_confidence(margin: float, threshold: float) -> float:
        """Maps "how far past the threshold" to a 0.6-1.0 confidence band -
        a rule-based classifier is never as calibrated as a trained model's
        softmax, so this is a deliberately conservative heuristic."""
        if threshold <= 0:
            return 0.6
        return float(min(1.0, 0.6 + 0.4 * (margin / threshold)))
