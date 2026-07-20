"""Manual robot control for testing - routes through the exact same
validator/safety chain as voice and gesture commands. Never calls the
robot controller directly."""
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class RobotPanel(QWidget):
    def __init__(self, service_workers, parent=None):
        super().__init__(parent)
        self._workers = service_workers

        layout = QVBoxLayout(self)

        grid = QGridLayout()
        buttons = [
            ("Forward", "go", 0, 1),
            ("Left", "left", 1, 0),
            ("Stop", "stop", 1, 1),
            ("Right", "right", 1, 2),
            ("Turn around", "back", 2, 1),
        ]
        for label, word, row, col in buttons:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, w=word: self._workers.submit_manual_command(w))
            grid.addWidget(button, row, col)
        layout.addLayout(grid)

        self.emergency_button = QPushButton("EMERGENCY STOP")
        self.emergency_button.setStyleSheet(
            "background-color: #b00020; color: white; font-weight: 700; padding: 8px;"
        )
        self.emergency_button.clicked.connect(self._workers.trigger_emergency_stop)
        layout.addWidget(self.emergency_button)

        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self._workers.clear_emergency_stop)
        layout.addWidget(self.resume_button)

        self.state_label = QLabel("Robot state: idle | mode: stop")
        layout.addWidget(self.state_label)

        self.safety_label = QLabel("Safety: normal")
        layout.addWidget(self.safety_label)

        layout.addStretch(1)

    @Slot(str, str)
    def update_robot_state(self, state: str, mode: str) -> None:
        self.state_label.setText(f"Robot state: {state} | mode: {mode}")

    @Slot(bool)
    def update_emergency_state(self, active: bool) -> None:
        self.safety_label.setText("Safety: EMERGENCY STOP ACTIVE" if active else "Safety: normal")
        self.safety_label.setStyleSheet("color: #b00020; font-weight: 700;" if active else "")
