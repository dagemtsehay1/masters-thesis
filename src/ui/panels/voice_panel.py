"""Voice command status + waveform visualizer."""
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src.ui.state import VoiceUIState
from src.ui.widgets.waveform_widget import WaveformWidget


class VoicePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.title_label = QLabel("Voice Wave")
        self.title_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.title_label)

        self.waveform = WaveformWidget(self)
        layout.addWidget(self.waveform, stretch=1)

        self.status_label = QLabel("Listening: no | Command: - | Confidence: -")
        layout.addWidget(self.status_label)

        self.transcript_label = QLabel("Transcript: -")
        layout.addWidget(self.transcript_label)

    @Slot(object)
    def update_voice_state(self, state: VoiceUIState) -> None:
        self.waveform.set_active(state.listening)
        language = f" [{state.language}]" if state.language else ""
        self.status_label.setText(
            f"Listening: {'yes' if state.listening else 'no'} | "
            f"Command: {state.transcript or '-'}{language} | Confidence: {state.confidence:.2f}"
        )
        self.transcript_label.setText(f"Transcript: {state.transcript or '-'}")

    @Slot(object)
    def update_waveform(self, samples) -> None:
        self.waveform.push_samples(samples)
