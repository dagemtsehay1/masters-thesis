"""The landing view: a compact summary of everything else, not a copy of
every panel's full controls - per the plan, "avoid placing every setting
on the main dashboard"."""
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui.state import CommandUIState, GestureUIState, VoiceUIState


class DashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>System Overview</h3>"))

        self.voice_label = QLabel("Voice: -")
        self.gesture_label = QLabel("Gesture: -")
        self.command_label = QLabel("Last command: -")
        self.robot_label = QLabel("Robot: idle")
        self.emergency_label = QLabel("Safety: normal")
        self.warning_label = QLabel("Recent warnings: none")
        self.warning_label.setWordWrap(True)

        for widget in (
            self.voice_label,
            self.gesture_label,
            self.command_label,
            self.robot_label,
            self.emergency_label,
            self.warning_label,
        ):
            layout.addWidget(widget)

        layout.addStretch(1)

    @Slot(object)
    def update_voice_state(self, state: VoiceUIState) -> None:
        self.voice_label.setText(f"Voice: {state.transcript or '-'} (listening={state.listening})")

    @Slot(object)
    def update_gesture_state(self, state: GestureUIState) -> None:
        self.gesture_label.setText(f"Gesture: {state.gesture or '-'} ({state.state})")

    @Slot(object)
    def update_command_state(self, state: CommandUIState) -> None:
        if state.status == "validated":
            self.command_label.setText(f"Last command: {state.action}/{state.direction} [{state.source}]")
        elif state.status == "rejected":
            self.command_label.setText(f"Last command rejected: {state.rejection_reason}")

    @Slot(str, str)
    def update_robot_state(self, robot_state: str, mode: str) -> None:
        self.robot_label.setText(f"Robot: {robot_state} ({mode})")

    @Slot(bool)
    def update_emergency_state(self, active: bool) -> None:
        self.emergency_label.setText("Safety: EMERGENCY STOP ACTIVE" if active else "Safety: normal")
        self.emergency_label.setStyleSheet("color: #b00020; font-weight: 700;" if active else "")

    @Slot(str, str, str)
    def note_log_message(self, level: str, component: str, message: str) -> None:
        if level.upper() in ("WARNING", "ERROR", "CRITICAL"):
            self.warning_label.setText(f"Recent warnings: [{component}] {message}")
