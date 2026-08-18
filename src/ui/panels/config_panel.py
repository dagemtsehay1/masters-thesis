"""Configuration view: runtime-editable settings, plus browsing/export of
the full active config.

Two groups, matching main.txt's "Where runtime modification is supported by
the interface, the new value is validated before it is applied":

  - "Live settings" take effect immediately. Every control here is bound to
    a config field that a running component reads live (the fusion engine,
    safety controller, and command validator all hold a reference to the
    same config objects rather than a copy - see Application.__init__) or
    that the component exposes a setter for (IntentEngine's confidence
    threshold, GestureSmoother's confirmation settings, CoppeliaClient's
    endpoint). Each widget's own range/type IS the validation - a spin box
    physically cannot submit an out-of-range value - and the underlying
    pydantic models additionally re-validate on assignment
    (`validate_assignment=True`, src/config/schema.py) as a second layer.

  - "Restart required" edits values that only take effect the next time
    `start_services()` runs (device indices, which modality is enabled,
    the Whisper model) - editing them here still validates and stores the
    value, it just doesn't hot-swap a running Whisper/MediaPipe/audio
    instance.

The browse/export tree below both groups is unchanged - useful for
inspecting fields that aren't exposed as dedicated controls.
"""
import json
import logging
from typing import Callable, get_args

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from src.config.schema import FusionMode

logger = logging.getLogger("ui.config_panel")

_FUSION_MODES = list(get_args(FusionMode))
_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
_LANGUAGE_MODES = ["auto", "en", "am"]


class ConfigPanel(QWidget):
    """The whole page scrolls as one unit (via the QScrollArea below)
    rather than the browse tree scrolling separately inside a fixed-height
    panel - the tree is sized to its full content height (see
    `_resize_tree_to_contents`) and grows/shrinks with what's filtered in,
    so every setting - live, restart-required, and browsed - stays reachable
    by a single scrollbar."""

    def __init__(self, application, workers=None, parent=None):
        super().__init__(parent)
        self._app = application
        self._workers = workers

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)
        layout = QVBoxLayout(content)

        layout.addWidget(QLabel("<h3>Configuration</h3>"))

        top = QHBoxLayout()
        active_preset = application.config.general.active_preset or "default"
        top.addWidget(QLabel(f"Active preset: {active_preset}"))
        top.addStretch(1)
        export_button = QPushButton("Export config")
        export_button.clicked.connect(self._export)
        top.addWidget(export_button)
        layout.addLayout(top)

        layout.addWidget(self._build_live_group())
        layout.addWidget(self._build_restart_group())

        layout.addWidget(QLabel("<b>Browse full configuration</b>"))
        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter settings...")
        self.search_box.textChanged.connect(self._render_tree)
        search_row.addWidget(self.search_box)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Setting", "Value"])
        self.tree.setColumnWidth(0, 320)
        # The tree grows to fit all its rows (see _resize_tree_to_contents)
        # instead of scrolling internally - the page's own QScrollArea
        # above is what scrolls, so its own scrollbar stays off and it
        # never fights the outer one for the wheel/drag.
        self.tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.tree)

        self._render_tree()

    # ================= LIVE SETTINGS =================

    def _build_live_group(self) -> QGroupBox:
        cfg = self._app.config
        group = QGroupBox("Live settings (apply immediately)")
        form = QFormLayout(group)

        self.fusion_mode_combo = self._combo(_FUSION_MODES, cfg.fusion.mode, self._set_fusion_mode)
        form.addRow("Fusion mode", self.fusion_mode_combo)

        form.addRow("Voice minimum confidence", self._double_spin(
            0.0, 1.0, 0.05, cfg.fusion.minimum_confidence.voice, self._set_voice_min_confidence))
        form.addRow("Gesture minimum confidence", self._double_spin(
            0.0, 1.0, 0.05, cfg.fusion.minimum_confidence.gesture, self._set_gesture_min_confidence))
        form.addRow("Voice acceptance threshold", self._double_spin(
            0.0, 1.0, 0.05, cfg.speech.confidence_threshold, self._set_voice_confidence_threshold))

        form.addRow("Duplicate-command cooldown (ms)", self._int_spin(
            0, 60000, 100, cfg.fusion.duplicate_command_cooldown_ms, self._set_duplicate_cooldown))
        form.addRow("Stale-event timeout (ms)", self._int_spin(
            0, 60000, 100, cfg.fusion.stale_event_timeout_ms, self._set_stale_timeout))

        form.addRow("Gesture confirmation frames", self._int_spin(
            1, 60, 1, cfg.gesture.confirmation_frames, self._set_confirmation_frames))
        form.addRow("Gesture cooldown (ms)", self._int_spin(
            0, 10000, 100, cfg.gesture.cooldown_ms, self._set_gesture_cooldown))

        form.addRow("Robot linear speed", self._double_spin(
            0.1, cfg.robot.max_linear_speed, 0.1, cfg.robot.linear_speed, self._set_linear_speed))
        form.addRow("Robot angular speed", self._double_spin(
            0.1, cfg.robot.max_angular_speed, 0.1, cfg.robot.angular_speed, self._set_angular_speed))
        form.addRow("Rotation tolerance (deg)", self._double_spin(
            0.1, 30.0, 0.5, cfg.robot.rotation_tolerance_deg, self._set_rotation_tolerance))
        form.addRow("Dead-man timeout (s)", self._double_spin(
            0.5, 60.0, 0.5, cfg.safety.dead_man_timeout_s, self._set_dead_man_timeout))

        self.qwen_checkbox = QCheckBox("Enabled")
        self.qwen_checkbox.setChecked(cfg.intent.qwen.enabled)
        self.qwen_checkbox.toggled.connect(self._set_qwen_enabled)
        form.addRow("Qwen3 local-LLM fallback", self.qwen_checkbox)

        coppelia_row = QWidget()
        coppelia_layout = QHBoxLayout(coppelia_row)
        coppelia_layout.setContentsMargins(0, 0, 0, 0)
        self.coppelia_host_edit = QLineEdit(cfg.coppelia.host)
        self.coppelia_host_edit.setPlaceholderText("host")
        self.coppelia_port_spin = QSpinBox()
        self.coppelia_port_spin.setRange(1, 65535)
        self.coppelia_port_spin.setValue(cfg.coppelia.port)
        reconnect_button = QPushButton("Apply && Reconnect")
        reconnect_button.clicked.connect(self._apply_coppelia_endpoint)
        coppelia_layout.addWidget(self.coppelia_host_edit)
        coppelia_layout.addWidget(QLabel(":"))
        coppelia_layout.addWidget(self.coppelia_port_spin)
        coppelia_layout.addWidget(reconnect_button)
        form.addRow("CoppeliaSim endpoint", coppelia_row)

        form.addRow("Logging level", self._combo(_LOG_LEVELS, cfg.logging.level.upper(), self._set_log_level))

        return group

    # ================= RESTART-REQUIRED SETTINGS =================

    def _build_restart_group(self) -> QGroupBox:
        cfg = self._app.config
        group = QGroupBox("Modality / device settings (apply on next Start)")
        form = QFormLayout(group)

        self.voice_enabled_checkbox = QCheckBox("Voice recognition enabled")
        self.voice_enabled_checkbox.setChecked(cfg.voice.enabled)
        self.voice_enabled_checkbox.toggled.connect(self._set_voice_enabled)
        form.addRow(self.voice_enabled_checkbox)

        self.gesture_enabled_checkbox = QCheckBox("Gesture recognition enabled")
        self.gesture_enabled_checkbox.setChecked(cfg.gesture.enabled)
        self.gesture_enabled_checkbox.toggled.connect(self._set_gesture_enabled)
        form.addRow(self.gesture_enabled_checkbox)

        self.mic_device_edit = QLineEdit("" if cfg.microphone.device_index is None else str(cfg.microphone.device_index))
        self.mic_device_edit.setPlaceholderText("system default")
        self.mic_device_edit.editingFinished.connect(self._set_microphone_device)
        form.addRow("Microphone device index", self.mic_device_edit)

        form.addRow("Camera device index", self._int_spin(
            0, 16, 1, cfg.camera.device_index, self._set_camera_device))

        form.addRow("Voice language", self._combo(
            _LANGUAGE_MODES, cfg.speech.languages.mode, self._set_language_mode))

        self.whisper_model_edit = QLineEdit(cfg.speech.whisper.model)
        self.whisper_model_edit.editingFinished.connect(self._set_whisper_model)
        form.addRow("Whisper model size", self.whisper_model_edit)

        note = QLabel("Restart services (Start System) for changes in this group to take effect.")
        note.setStyleSheet("color: #888; font-style: italic;")
        form.addRow(note)

        return group

    # ================= WIDGET FACTORIES =================

    def _combo(self, options, current: str, on_change: Callable[[str], None]) -> QComboBox:
        box = QComboBox()
        box.addItems(options)
        if current in options:
            box.setCurrentText(current)
        box.currentTextChanged.connect(on_change)
        return box

    def _double_spin(self, lo: float, hi: float, step: float, current: float, on_change: Callable[[float], None]) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(lo, hi)
        box.setSingleStep(step)
        box.setDecimals(2)
        box.setValue(current)
        box.valueChanged.connect(on_change)
        return box

    def _int_spin(self, lo: int, hi: int, step: int, current: int, on_change: Callable[[int], None]) -> QSpinBox:
        box = QSpinBox()
        box.setRange(lo, hi)
        box.setSingleStep(step)
        box.setValue(current)
        box.valueChanged.connect(on_change)
        return box

    # ================= LIVE SETTING HANDLERS =================
    # Each handler applies the value to the live config object (validated by
    # pydantic's validate_assignment) and, where the consuming component
    # only reads a snapshot instead of the config object itself, also pushes
    # it through that component's setter. A rejected value (should only
    # happen if a widget's own range still permits something the pydantic
    # model doesn't - defense in depth) is reported and the widget is left
    # showing the value the user tried to enter; nothing crashes.

    def _apply(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except ValidationError as exc:
            logger.warning("Rejected configuration change: %s", exc)
            QMessageBox.warning(self, "Invalid value", str(exc))

    def _set_fusion_mode(self, mode: str) -> None:
        self._apply(lambda: setattr(self._app.config.fusion, "mode", mode))

    def _set_voice_min_confidence(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.fusion.minimum_confidence, "voice", value))

    def _set_gesture_min_confidence(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.fusion.minimum_confidence, "gesture", value))

    def _set_voice_confidence_threshold(self, value: float) -> None:
        def do():
            self._app.config.speech.confidence_threshold = value
            if self._app.voice is not None:
                self._app.voice._intent_engine.set_confidence_threshold(value)
        self._apply(do)

    def _set_duplicate_cooldown(self, value: int) -> None:
        self._apply(lambda: setattr(self._app.config.fusion, "duplicate_command_cooldown_ms", value))

    def _set_stale_timeout(self, value: int) -> None:
        self._apply(lambda: setattr(self._app.config.fusion, "stale_event_timeout_ms", value))

    def _set_confirmation_frames(self, value: int) -> None:
        def do():
            self._app.config.gesture.confirmation_frames = value
            if self._app.gesture is not None:
                self._app.gesture.smoother.set_confirmation_frames(value)
        self._apply(do)

    def _set_gesture_cooldown(self, value: int) -> None:
        def do():
            self._app.config.gesture.cooldown_ms = value
            if self._app.gesture is not None:
                self._app.gesture.smoother.set_cooldown_s(value / 1000.0)
        self._apply(do)

    def _set_linear_speed(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.robot, "linear_speed", value))

    def _set_angular_speed(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.robot, "angular_speed", value))

    def _set_rotation_tolerance(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.robot, "rotation_tolerance_deg", value))

    def _set_dead_man_timeout(self, value: float) -> None:
        self._apply(lambda: setattr(self._app.config.safety, "dead_man_timeout_s", value))

    def _set_qwen_enabled(self, enabled: bool) -> None:
        def do():
            self._app.config.intent.qwen.enabled = enabled
            # Refresh the "ollama" header badge to match - off the UI
            # thread if services are running (health_check() is a blocking
            # HTTP call), otherwise there's no client yet for it to matter.
            if self._workers is not None:
                self._workers.request_qwen_recheck()
        self._apply(do)

    def _apply_coppelia_endpoint(self) -> None:
        host = self.coppelia_host_edit.text().strip() or "localhost"
        port = self.coppelia_port_spin.value()

        def do():
            self._app.config.coppelia.host = host
            self._app.config.coppelia.port = port
            if self._app.client is None:
                QMessageBox.information(self, "CoppeliaSim", "Endpoint saved; connect via Start System.")
                return
            if self._workers is not None:
                # Reconnecting is blocking network I/O with retries (see
                # CoppeliaClient.connect()) - run it on the robot thread via
                # a queued signal instead of blocking the UI thread here.
                # The outcome is reported through the log panel.
                self._workers.request_coppelia_reconnect(host, port)
            else:
                self._app.client.set_endpoint(host, port)
                self._app.client.reconnect()
        self._apply(do)

    def _set_log_level(self, level: str) -> None:
        from src.monitoring.logging_setup import set_level

        def do():
            self._app.config.logging.level = level
            set_level(level)
        self._apply(do)

    # ================= RESTART-REQUIRED SETTING HANDLERS =================

    def _set_voice_enabled(self, enabled: bool) -> None:
        self._apply(lambda: setattr(self._app.config.voice, "enabled", enabled))

    def _set_gesture_enabled(self, enabled: bool) -> None:
        self._apply(lambda: setattr(self._app.config.gesture, "enabled", enabled))

    def _set_microphone_device(self) -> None:
        text = self.mic_device_edit.text().strip()
        value = None if not text else int(text) if text.lstrip("-").isdigit() else None
        if text and value is None:
            QMessageBox.warning(self, "Invalid value", "Microphone device index must be an integer, or blank for default.")
            return
        self._apply(lambda: setattr(self._app.config.microphone, "device_index", value))

    def _set_camera_device(self, value: int) -> None:
        self._apply(lambda: setattr(self._app.config.camera, "device_index", value))

    def _set_language_mode(self, mode: str) -> None:
        self._apply(lambda: setattr(self._app.config.speech.languages, "mode", mode))

    def _set_whisper_model(self) -> None:
        model = self.whisper_model_edit.text().strip()
        if not model:
            return
        self._apply(lambda: setattr(self._app.config.speech.whisper, "model", model))

    # ================= BROWSE / EXPORT =================

    def _config_dict(self) -> dict:
        return self._app.config.model_dump()

    def _render_tree(self, *_args) -> None:
        query = self.search_box.text().strip().lower()
        self.tree.clear()
        for section, values in self._config_dict().items():
            section_item = QTreeWidgetItem([section, ""])
            matched_any = self._populate(section_item, values, query, path=section)
            if query and not matched_any and query not in section.lower():
                continue
            self.tree.addTopLevelItem(section_item)
        self._resize_tree_to_contents()

    def _resize_tree_to_contents(self) -> None:
        """Sizes the tree to fit every row instead of scrolling internally -
        everything expanded is visible at once, and the page's own
        QScrollArea is what scrolls past it (see the class docstring)."""
        self.tree.expandAll()

        row_count = 0
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            row_count += 1
            iterator += 1

        row_height = self.tree.sizeHintForRow(0) if row_count else 20
        header_height = self.tree.header().sizeHint().height()
        self.tree.setFixedHeight(header_height + row_count * row_height + 4)

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
