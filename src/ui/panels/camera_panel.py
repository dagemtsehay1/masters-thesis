"""Live camera preview + gesture status."""
import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui.state import GestureUIState


class CameraPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.preview_label = QLabel("Camera disabled or unavailable")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 240)
        self.preview_label.setStyleSheet("background-color: #202020; color: #aaaaaa; border-radius: 6px;")
        layout.addWidget(self.preview_label, stretch=1)

        self.status_label = QLabel("Gesture: - | Confidence: - | Hand: - | State: -")
        layout.addWidget(self.status_label)

        self.progress_label = QLabel("Confirmation: 0/0")
        layout.addWidget(self.progress_label)

    @Slot(object)
    def update_frame(self, frame: np.ndarray) -> None:
        if frame is None:
            return
        height, width, _ = frame.shape
        rgb = frame[:, :, ::-1].copy()  # BGR -> RGB without an extra cv2 dependency here
        image = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(pixmap)

    @Slot(object)
    def update_gesture_state(self, state: GestureUIState) -> None:
        hand = state.handedness or "-"
        gesture = state.gesture or "-"
        self.status_label.setText(
            f"Gesture: {gesture} | Confidence: {state.confidence:.2f} | Hand: {hand} | State: {state.state}"
        )
        self.progress_label.setText(
            f"Confirmation: {state.confirmation_progress}/{state.confirmation_required}"
        )
