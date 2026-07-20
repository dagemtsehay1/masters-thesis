"""A small colored status pill used in the header and diagnostics panel."""
from PySide6.QtWidgets import QLabel

_COLORS = {
    "ready": "#2f9e44",
    "starting": "#f08c00",
    "active": "#2f9e44",
    "disabled": "#868e96",
    "degraded": "#f08c00",
    "error": "#e03131",
    "disconnected": "#e03131",
}


class StatusBadge(QLabel):
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._name = name
        self.setMinimumWidth(90)
        self.set_state("disabled", "-")

    def set_state(self, state: str, message: str = "") -> None:
        color = _COLORS.get(state, "#868e96")
        self.setText(f"{self._name}: {state}")
        self.setToolTip(message or state)
        self.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 4px; "
            "padding: 3px 8px; font-size: 11px; font-weight: 600;"
        )
