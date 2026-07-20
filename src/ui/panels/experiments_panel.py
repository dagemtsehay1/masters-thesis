"""Experiment/thesis mode: record per-trial expected-vs-recognized results
and export them to CSV/JSON. Participant tracking is off by default; no
audio or video is ever stored - only the derived fields entered here."""
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.monitoring.experiment_log import ExperimentLog, Trial


class ExperimentsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._log = ExperimentLog()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Experiment Mode</h3>"))

        meta = QFormLayout()
        self.experiment_name = QLineEdit()
        self.session_id = QLineEdit()
        self.session_id.setPlaceholderText("optional - participant tracking off by default")
        meta.addRow("Experiment name", self.experiment_name)
        meta.addRow("Session / participant", self.session_id)
        layout.addLayout(meta)

        trial_form = QFormLayout()
        self.expected = QLineEdit()
        self.recognized = QLineEdit()
        self.modality = QComboBox()
        self.modality.addItems(["voice", "gesture", "combined", "manual"])
        self.language = QComboBox()
        self.language.addItems(["en", "am"])
        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.0, 1.0)
        self.confidence.setSingleStep(0.05)
        self.latency = QDoubleSpinBox()
        self.latency.setRange(0.0, 100000.0)
        self.noise = QLineEdit()
        self.lighting = QLineEdit()
        self.notes = QLineEdit()
        trial_form.addRow("Expected command", self.expected)
        trial_form.addRow("Recognized command", self.recognized)
        trial_form.addRow("Modality", self.modality)
        trial_form.addRow("Language", self.language)
        trial_form.addRow("Confidence", self.confidence)
        trial_form.addRow("Latency (ms)", self.latency)
        trial_form.addRow("Noise condition", self.noise)
        trial_form.addRow("Lighting condition", self.lighting)
        trial_form.addRow("Notes", self.notes)
        layout.addLayout(trial_form)

        buttons = QHBoxLayout()
        add_button = QPushButton("Add trial")
        add_button.clicked.connect(self._add_trial)
        buttons.addWidget(add_button)
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(self._export_csv)
        buttons.addWidget(export_csv)
        export_json = QPushButton("Export JSON")
        export_json.clicked.connect(self._export_json)
        buttons.addWidget(export_json)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Expected", "Recognized", "Correct", "Modality", "Latency"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        self.accuracy_label = QLabel("Accuracy: -")
        layout.addWidget(self.accuracy_label)

    def _add_trial(self) -> None:
        expected = self.expected.text().strip()
        recognized = self.recognized.text().strip() or None
        if not expected:
            return

        trial = Trial(
            expected_command=expected,
            recognized_command=recognized,
            correct=(recognized == expected),
            modality=self.modality.currentText(),
            language=self.language.currentText(),
            confidence=self.confidence.value(),
            latency_ms=self.latency.value(),
            noise_condition=self.noise.text().strip(),
            lighting_condition=self.lighting.text().strip(),
            notes=self.notes.text().strip(),
        )
        self._log.add_trial(trial)
        self._append_row(trial)
        accuracy = self._log.accuracy()
        self.accuracy_label.setText(f"Accuracy: {accuracy:.1%}" if accuracy is not None else "Accuracy: -")

    def _append_row(self, trial: Trial) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            trial.expected_command,
            trial.recognized_command or "-",
            "yes" if trial.correct else "no",
            trial.modality,
            f"{trial.latency_ms:.0f}",
        ]
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))

    def _sync_metadata(self) -> None:
        self._log.experiment_name = self.experiment_name.text().strip()
        self._log.session_id = self.session_id.text().strip()

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export experiment CSV", "experiment.csv", "CSV files (*.csv)")
        if path:
            self._sync_metadata()
            self._log.export_csv(path)

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export experiment JSON", "experiment.json", "JSON files (*.json)")
        if path:
            self._sync_metadata()
            self._log.export_json(path)
