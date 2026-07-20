"""Structured, bounded log viewer.

Keeps at most `max_visible` entries in memory for display - this is
explicitly *not* the full application log (that goes to
src/monitoring/logging_setup.py's handlers/file); it's just the UI's own
bounded recent-activity view, so it can never grow without limit.
"""
from collections import deque
from datetime import datetime

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

_LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_COMPONENTS = ["ALL", "voice", "gesture", "fusion", "robot", "coppelia", "ollama", "performance", "safety", "app"]


class LogPanel(QWidget):
    def __init__(self, parent=None, max_visible: int = 1000):
        super().__init__(parent)
        self._max_visible = max_visible
        self._entries = deque(maxlen=max_visible)
        self._paused = False

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.level_filter = QComboBox()
        self.level_filter.addItems(_LEVELS)
        self.level_filter.currentTextChanged.connect(self._render)
        controls.addWidget(self.level_filter)

        self.component_filter = QComboBox()
        self.component_filter.addItems(_COMPONENTS)
        self.component_filter.currentTextChanged.connect(self._render)
        controls.addWidget(self.component_filter)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.textChanged.connect(self._render)
        controls.addWidget(self.search_box, stretch=1)

        self.pause_button = QPushButton("Pause auto-scroll")
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self._on_pause_toggled)
        controls.addWidget(self.pause_button)

        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear)
        controls.addWidget(clear_button)

        copy_button = QPushButton("Copy selected")
        copy_button.clicked.connect(self._copy_selected)
        controls.addWidget(copy_button)

        export_button = QPushButton("Export")
        export_button.clicked.connect(self._export)
        controls.addWidget(export_button)

        layout.addLayout(controls)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Time", "Level", "Component", "Message"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

    def _on_pause_toggled(self, checked: bool) -> None:
        self._paused = checked

    @Slot(str, str, str)
    def append_log(self, level: str, component: str, message: str) -> None:
        self._entries.append((datetime.now().strftime("%H:%M:%S"), level.upper(), component, message))
        self._render()

    def _matches_filters(self, entry) -> bool:
        _, level, component, message = entry
        if self.level_filter.currentText() != "ALL" and level != self.level_filter.currentText():
            return False
        if self.component_filter.currentText() != "ALL" and component != self.component_filter.currentText():
            return False
        query = self.search_box.text().strip().lower()
        if query and query not in message.lower() and query not in component.lower():
            return False
        return True

    def _render(self, *_args) -> None:
        rows = [entry for entry in self._entries if self._matches_filters(entry)]
        self.table.setRowCount(len(rows))
        for row_idx, (timestamp, level, component, message) in enumerate(rows):
            for col_idx, value in enumerate((timestamp, level, component, message)):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        if not self._paused:
            self.table.scrollToBottom()

    def _clear(self) -> None:
        self._entries.clear()
        self._render()

    def _copy_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        lines = [
            "\t".join(self.table.item(row, col).text() for col in range(self.table.columnCount()))
            for row in rows
        ]
        QApplication.clipboard().setText("\n".join(lines))

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export logs", "logs.csv", "CSV files (*.csv)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write("time,level,component,message\n")
            for timestamp, level, component, message in self._entries:
                safe_message = message.replace('"', '""')
                f.write(f'{timestamp},{level},{component},"{safe_message}"\n')
