"""Diagnostics: run component health checks and a short benchmark from the
UI. The health check never moves the robot (its robot check only sends a
stop); a movement test would be a separate explicit action."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.monitoring import health

_STATUS_COLOR = {"pass": "#2f9e44", "warn": "#f08c00", "fail": "#e03131"}


class DiagnosticsPanel(QWidget):
    def __init__(self, application, parent=None):
        super().__init__(parent)
        self._app = application

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Diagnostics</h3>"))

        controls = QHBoxLayout()
        self.health_button = QPushButton("Run system health check")
        self.health_button.clicked.connect(self._run_health_check)
        controls.addWidget(self.health_button)

        self.benchmark_button = QPushButton("Run short benchmark")
        self.benchmark_button.clicked.connect(self._run_benchmark)
        controls.addWidget(self.benchmark_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Check", "Result", "Detail"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results_table, stretch=1)

        self.benchmark_label = QLabel("Benchmark: not run")
        layout.addWidget(self.benchmark_label)

    def _run_health_check(self) -> None:
        if self._app.controller is None:
            self._set_results([("system", "warn", "Start the system before running health checks")])
            return
        results = health.run_all(self._app)
        self._set_results([(r.name, r.status, r.message) for r in results])

    def _run_benchmark(self) -> None:
        # A short, safe in-process benchmark: time a batch of fusion
        # resolutions (the one component that's always available and never
        # touches hardware). Whisper/gesture latency benchmarks that need
        # real models live in tests/benchmarks/ and run from the CLI.
        import time

        from src.gesture.events import GestureEvent
        from src.voice.events import VoiceEvent

        voice = VoiceEvent(command="go")
        gesture = GestureEvent(gesture="left", state="confirmed")
        iterations = 5000
        start = time.perf_counter()
        for i in range(iterations):
            self._app.fusion.resolve(voice, gesture, now=time.time() + i)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.benchmark_label.setText(
            f"Benchmark: {iterations} fusion resolutions in {elapsed_ms:.1f} ms "
            f"({elapsed_ms / iterations * 1000:.2f} us each)"
        )

    def _set_results(self, rows) -> None:
        self.results_table.setRowCount(len(rows))
        for row_idx, (name, status, message) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(Qt.GlobalColor.white)
            status_item.setData(Qt.ItemDataRole.BackgroundRole, None)
            detail_item = QTableWidgetItem(message)
            self.results_table.setItem(row_idx, 0, name_item)
            self.results_table.setItem(row_idx, 1, status_item)
            self.results_table.setItem(row_idx, 2, detail_item)
            color = _STATUS_COLOR.get(status)
            if color:
                status_item.setToolTip(status)
                status_item.setForeground(Qt.GlobalColor.black)
