"""Shows the command pipeline (voice/gesture -> fusion -> validation) and
lets the fusion mode be changed live."""
from typing import get_args

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from src.config.schema import FusionMode
from src.ui.state import CommandUIState

_MODES = list(get_args(FusionMode))

_BADGE_TEXT = {
    "voice": "Voice",
    "gesture": "Gesture",
    "combined": "Combined",
    "emergency": "Emergency",
    "manual": "Manual",
}


class CommandFusionPanel(QWidget):
    def __init__(self, application, parent=None):
        super().__init__(parent)
        self._app = application

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(_MODES)
        self.mode_combo.setCurrentText(application.config.fusion.mode)
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Fusion mode", self.mode_combo)
        layout.addWidget(QLabel("Fusion configuration"))
        layout.addLayout(form)

        self.pipeline_label = QLabel("Input -> Recognition -> Fusion -> Safety -> Robot")
        self.pipeline_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.pipeline_label)

        self.decision_label = QLabel("Last decision: -")
        layout.addWidget(self.decision_label)

        self.rejection_label = QLabel("Last rejection: -")
        layout.addWidget(self.rejection_label)

        layout.addStretch(1)

    def _on_mode_changed(self, mode: str) -> None:
        self._app.config.fusion.mode = mode

    @Slot(object)
    def update_command_state(self, state: CommandUIState) -> None:
        if state.status == "none":
            return

        badge = _BADGE_TEXT.get(state.source, state.source or "-")
        if state.status == "validated":
            self.decision_label.setText(
                f"Last decision: [{badge}] {state.action}/{state.direction} (confidence {state.confidence:.2f})"
            )
        else:
            self.rejection_label.setText(
                f"Last rejection: [{badge}] {state.action}/{state.direction} - {state.rejection_reason}"
            )
