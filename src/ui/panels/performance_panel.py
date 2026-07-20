"""Performance dashboard: CPU/memory sparklines + recent-value indicators.

Redraws on a fixed timer (`ui.metrics_refresh_ms`), not per-sample, and
every series is bounded (`ui.chart_history_samples`). Can be disabled
entirely via `ui.show_performance_monitor` for the low-resource preset.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from src.ui.widgets.sparkline_widget import SparklineWidget


class PerformancePanel(QWidget):
    def __init__(self, application, parent=None):
        super().__init__(parent)
        self._app = application
        self._metrics = application.metrics
        ui_cfg = application.config.ui

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Performance</h3>"))

        if not ui_cfg.show_performance_monitor:
            layout.addWidget(QLabel("Performance monitoring disabled by configuration."))
            layout.addStretch(1)
            return

        history = ui_cfg.chart_history_samples

        self.cpu_spark = SparklineWidget(history_size=history, color="#1971c2")
        self.cpu_spark.set_fixed_range(0, 100)
        self.mem_spark = SparklineWidget(history_size=history, color="#2f9e44")

        layout.addWidget(QLabel("CPU %"))
        layout.addWidget(self.cpu_spark)
        layout.addWidget(QLabel("Memory (MB)"))
        layout.addWidget(self.mem_spark)

        form = QFormLayout()
        self.cpu_value = QLabel("-")
        self.mem_value = QLabel("-")
        self.uptime_value = QLabel("-")
        self.gesture_latency_value = QLabel("-")
        self.whisper_latency_value = QLabel("-")
        self.commands_value = QLabel("-")
        form.addRow("CPU", self.cpu_value)
        form.addRow("Memory", self.mem_value)
        form.addRow("Uptime", self.uptime_value)
        form.addRow("Gesture latency", self.gesture_latency_value)
        form.addRow("Whisper latency", self.whisper_latency_value)
        form.addRow("Commands executed", self.commands_value)
        layout.addLayout(form)

        layout.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(ui_cfg.metrics_refresh_ms)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        sample = self._metrics.sample_system()
        cpu, memory_mb = sample["cpu_percent"], sample["memory_mb"]

        if cpu is not None:
            self.cpu_spark.add_sample(cpu)
            self.cpu_value.setText(f"{cpu:.0f} %")
        if memory_mb is not None:
            self.mem_spark.add_sample(memory_mb)
            self.mem_value.setText(f"{memory_mb:.0f} MB")

        self.uptime_value.setText(f"{self._metrics.uptime_s():.0f} s")

        gesture_latency = self._metrics.mean_latency("gesture")
        whisper_latency = self._metrics.mean_latency("whisper")
        self.gesture_latency_value.setText(f"{gesture_latency:.0f} ms" if gesture_latency else "-")
        self.whisper_latency_value.setText(f"{whisper_latency:.0f} ms" if whisper_latency else "-")
        self.commands_value.setText(str(self._metrics.counter("commands_executed")))
