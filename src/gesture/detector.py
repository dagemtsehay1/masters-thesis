import time
import cv2
import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class GestureDetector:
    def __init__(self):
        self.cap = None
        self.last_timestamp_ms = 0

        # Load hand landmark model
        base_options = python.BaseOptions(
            model_asset_path="model/hand_landmarker.task"
        )

        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_tracking_confidence=0.6,
        )

        self.detector = vision.HandLandmarker.create_from_options(options)

    def start(self):
        self.cap = cv2.VideoCapture(0)

    def stop(self):
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()

    def _is_finger_up(self, landmarks, tip_idx, pip_idx):
        return landmarks[tip_idx].y < landmarks[pip_idx].y

    def _classify(self, landmarks):
        wrist = landmarks[0]

        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        index_up = self._is_finger_up(landmarks, 8, 6)
        middle_up = self._is_finger_up(landmarks, 12, 10)
        ring_up = self._is_finger_up(landmarks, 16, 14)
        pinky_up = self._is_finger_up(landmarks, 20, 18)

        fingers_up = [index_up, middle_up, ring_up, pinky_up]
        up_count = sum(fingers_up)

        # ✋ stop = open palm facing camera
        if up_count == 4:
            return "stop"

        # 👈 left / 👉 right = only index finger up
        if index_up and not middle_up and not ring_up and not pinky_up:
            dx = index_tip.x - wrist.x
            dy = index_tip.y - wrist.y

            if abs(dx) > abs(dy):
                if dx < -0.15:
                    return "left"
                if dx > 0.15:
                    return "right"

        # 🫴 go / 🫳 back = open hand with direction
        if up_count >= 3:
            avg_y = (
                index_tip.y +
                middle_tip.y +
                ring_tip.y +
                pinky_tip.y
            ) / 4.0

            # hand up
            if avg_y < wrist.y - 0.05:
                return "go"

            # hand down
            if avg_y > wrist.y + 0.05:
                return "back"

        return None

    def detect(self):
        if self.cap is None:
            return None

        ret, frame = self.cap.read()
        if not ret:
            return None

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        timestamp_ms = int(time.time() * 1000)
        if timestamp_ms <= self.last_timestamp_ms:
            timestamp_ms = self.last_timestamp_ms + 1
        self.last_timestamp_ms = timestamp_ms

        result = self.detector.detect_for_video(mp_image, timestamp_ms)

        command = None

        if result.hand_landmarks:
            for hand_landmarks in result.hand_landmarks:
                command = self._classify(hand_landmarks)

                h, w, _ = frame.shape
                for lm in hand_landmarks:
                    cx = int(lm.x * w)
                    cy = int(lm.y * h)
                    cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)

        cv2.putText(
            frame,
            f"Gesture: {command if command else '-'}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Gesture", frame)
        cv2.waitKey(1)

        return command