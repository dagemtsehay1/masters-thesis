"""A small bounded-history line chart for the performance dashboard.

Bounded to `history_size` samples and redrawn only when a new sample
arrives - never an unbounded, continuously-growing chart.
"""
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SparklineWidget(QWidget):
    def __init__(self, parent=None, history_size: int = 120, color: str = "#1971c2"):
        super().__init__(parent)
        self._history = deque(maxlen=history_size)
        self._color = QColor(color)
        self._min: Optional[float] = None
        self._max: Optional[float] = None
        self.setMinimumHeight(40)

    def set_fixed_range(self, minimum: float, maximum: float) -> None:
        self._min, self._max = minimum, maximum

    def add_sample(self, value: float) -> None:
        self._history.append(value)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#f8f9fa"))

        if len(self._history) < 2:
            return

        width, height = self.width(), self.height()
        values = list(self._history)
        lo = self._min if self._min is not None else min(values)
        hi = self._max if self._max is not None else max(values)
        span = (hi - lo) or 1.0

        painter.setPen(QPen(self._color, 2))
        prev = None
        for i, value in enumerate(values):
            x = i * (width / max(1, len(values) - 1))
            normalized = (value - lo) / span
            y = height - normalized * height
            if prev is not None:
                painter.drawLine(prev[0], prev[1], x, y)
            prev = (x, y)
