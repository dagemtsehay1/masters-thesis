"""A lightweight amplitude waveform, drawn with QPainter.

Deliberately not backed by a charting library (pyqtgraph/matplotlib would
be a heavy dependency for what's just a scrolling line) - a bounded deque
plus a paintEvent is enough. Feeding it real microphone amplitude is wired
up in Phase 5 once src/audio/capture.py's ring buffer exists; until then it
renders a flat idle line, which is itself useful feedback (distinguishes
"idle" from "listening" once real data starts arriving).
"""
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    def __init__(self, parent=None, history_size: int = 512):
        super().__init__(parent)
        self._samples = deque([0.0] * history_size, maxlen=history_size)
        self._active = False
        self.setMinimumHeight(80)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def push_samples(self, samples) -> None:
        self._samples.extend(float(s) for s in samples)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width, height = self.width(), self.height()
        center_y = height / 2.0

        painter.fillRect(self.rect(), QColor("#f3f3f3"))

        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.drawLine(0, int(center_y), width, int(center_y))

        line_color = QColor("#2f9e44") if self._active else QColor("#888888")
        painter.setPen(QPen(line_color, 2))

        samples = list(self._samples)
        if len(samples) < 2 or width <= 1:
            return

        step = max(1, len(samples) // max(1, width))
        reduced = samples[::step]
        scale = height * 0.4

        prev_point = None
        for i, sample in enumerate(reduced):
            x = i * (width / max(1, len(reduced) - 1))
            y = center_y - sample * scale
            if prev_point is not None:
                painter.drawLine(prev_point[0], prev_point[1], x, y)
            prev_point = (x, y)
