"""Configuration view: browse the active config, filter it, and export it.

Editing live/restart-required settings in place is deliberately limited
here - most fields (Whisper model, camera device, VAD backend) only take
effect at `start_services()` time, so this panel focuses on inspection,
preset awareness, and export/reload rather than pretending a change to a
model-load-time field applies instantly. Fusion mode - the one genuinely
hot-swappable setting - is editable from the Command & Fusion panel.
"""
import json

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ConfigPanel(QWidget):
    def __init__(self, application, parent=None):
        super().__init__(parent)
        self._app = application

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<h3>Configuration</h3>"))

        top = QHBoxLayout()
        active_preset = application.config.general.active_preset or "default"
        top.addWidget(QLabel(f"Active preset: {active_preset}"))
        top.addStretch(1)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter settings...")
        self.search_box.textChanged.connect(self._render)
        top.addWidget(self.search_box)

        export_button = QPushButton("Export config")
        export_button.clicked.connect(self._export)
        top.addWidget(export_button)
        layout.addLayout(top)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Setting", "Value"])
        self.tree.setColumnWidth(0, 320)
        layout.addWidget(self.tree, stretch=1)

        self._render()

    def _config_dict(self) -> dict:
        return self._app.config.model_dump()

    def _render(self, *_args) -> None:
        query = self.search_box.text().strip().lower()
        self.tree.clear()
        for section, values in self._config_dict().items():
            section_item = QTreeWidgetItem([section, ""])
            matched_any = self._populate(section_item, values, query, path=section)
            if query and not matched_any and query not in section.lower():
                continue
            self.tree.addTopLevelItem(section_item)
            section_item.setExpanded(bool(query))

    def _populate(self, parent_item, value, query, path) -> bool:
        matched = False
        if isinstance(value, dict):
            for key, sub_value in value.items():
                child = QTreeWidgetItem([str(key), ""])
                child_matched = self._populate(child, sub_value, query, path=f"{path}.{key}")
                full_path = f"{path}.{key}".lower()
                if not query or child_matched or query in full_path:
                    parent_item.addChild(child)
                    matched = matched or child_matched or (query in full_path)
        else:
            parent_item.setText(1, str(value))
            matched = not query or query in path.lower() or query in str(value).lower()
        return matched

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export configuration", "config.json", "JSON files (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._config_dict(), f, indent=2, default=str, ensure_ascii=False)
