"""The PySide6 desktop shell.

Owns no business logic: it renders `AppState`-shaped signals coming from
`ServiceWorkers` and forwards user actions (button clicks, dropdown
changes) back into `Application`/`ServiceWorkers` through the same
validated command path voice and gesture use - never directly into
`RobotController`.
"""
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.ui.panels.camera_panel import CameraPanel
from src.ui.panels.command_fusion_panel import CommandFusionPanel
from src.ui.panels.config_panel import ConfigPanel
from src.ui.panels.dashboard import DashboardPanel
from src.ui.panels.diagnostics_panel import DiagnosticsPanel
from src.ui.panels.experiments_panel import ExperimentsPanel
from src.ui.panels.log_panel import LogPanel
from src.ui.panels.performance_panel import PerformancePanel
from src.ui.panels.robot_panel import RobotPanel
from src.ui.panels.voice_panel import VoicePanel
from src.ui.widgets.status_badge import StatusBadge
from src.ui.workers import ServiceWorkers

logger = logging.getLogger("ui.main_window")

_NAV_ITEMS = [
    "Dashboard",
    "Camera & Gestures",
    "Voice Commands",
    "Robot Control",
    "Configuration",
    "Logs",
    "Performance",
    "Diagnostics",
    "Experiments",
]


class MainWindow(QMainWindow):
    def __init__(self, application):
        super().__init__()
        self.app = application
        self.workers = ServiceWorkers(application)

        config = application.config
        self.setWindowTitle(config.ui.window_title)
        self.resize(1200, 800)

        self._build_header()
        self._build_body()
        self._connect_workers()

        self.close_confirmed = False

    # ================= LAYOUT =================

    def _build_header(self) -> None:
        header = QWidget()
        layout = QHBoxLayout(header)

        config = self.app.config
        preset_text = config.general.active_preset or "default"

        self.title_label = QLabel(f"<b>{config.ui.window_title}</b>")
        layout.addWidget(self.title_label)

        layout.addWidget(QLabel(f"Mode: {config.general.app_mode}"))
        layout.addWidget(QLabel(f"Preset: {preset_text}"))
        layout.addWidget(QLabel("Offline"))
        languages = ", ".join(config.speech.languages.enabled)
        layout.addWidget(QLabel(f"Languages: {languages}"))
        self.fusion_mode_label = QLabel(f"Fusion: {config.fusion.mode}")
        layout.addWidget(self.fusion_mode_label)

        layout.addStretch(1)

        self.start_button = QPushButton("Start System")
        self.start_button.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_button)

        self.emergency_button = QPushButton("EMERGENCY STOP")
        self.emergency_button.setStyleSheet(
            "background-color: #b00020; color: white; font-weight: 700; padding: 6px 14px;"
        )
        self.emergency_button.clicked.connect(self.workers.trigger_emergency_stop)
        layout.addWidget(self.emergency_button)

        self.badges = {
            name: StatusBadge(name)
            for name in ("camera", "microphone", "whisper", "mediapipe", "ollama", "coppelia", "robot")
        }
        for badge in self.badges.values():
            layout.addWidget(badge)

        self.setMenuWidget(header)

    def _build_body(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)

        self.nav_list = QListWidget()
        self.nav_list.addItems(_NAV_ITEMS)
        self.nav_list.setFixedWidth(180)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        layout.addWidget(self.nav_list)

        self.dashboard = DashboardPanel()
        self.camera_panel = CameraPanel()
        self.voice_panel = VoicePanel()
        self.robot_panel = RobotPanel(self.workers)
        self.command_fusion_panel = CommandFusionPanel(self.app)
        self.config_panel = ConfigPanel(self.app, self.workers)
        self.log_panel = LogPanel(max_visible=self.app.config.ui.maximum_visible_logs)
        self.performance_panel = PerformancePanel(self.app)
        self.diagnostics_panel = DiagnosticsPanel(self.app)
        self.experiments_panel = ExperimentsPanel()

        self.content_stack = QStackedWidget()
        for widget in (
            self.dashboard,
            self.camera_panel,
            self.voice_panel,
            self.robot_panel,
            self.config_panel,
            self.log_panel,
            self.performance_panel,
            self.diagnostics_panel,
            self.experiments_panel,
        ):
            self.content_stack.addWidget(widget)

        layout.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(central)
        self.nav_list.setCurrentRow(0)

    def _connect_workers(self) -> None:
        w = self.workers
        w.frame_ready.connect(self.camera_panel.update_frame)
        w.gesture_state_changed.connect(self.camera_panel.update_gesture_state)
        w.gesture_state_changed.connect(self.dashboard.update_gesture_state)
        w.voice_state_changed.connect(self.voice_panel.update_voice_state)
        w.voice_state_changed.connect(self.dashboard.update_voice_state)
        w.waveform_ready.connect(self.voice_panel.update_waveform)
        w.command_state_changed.connect(self.command_fusion_panel.update_command_state)
        w.command_state_changed.connect(self.dashboard.update_command_state)
        w.robot_state_changed.connect(self.robot_panel.update_robot_state)
        w.robot_state_changed.connect(self.dashboard.update_robot_state)
        w.emergency_state_changed.connect(self.robot_panel.update_emergency_state)
        w.emergency_state_changed.connect(self.dashboard.update_emergency_state)
        w.emergency_state_changed.connect(self._on_emergency_state_changed)
        w.log_message.connect(self.log_panel.append_log)
        w.log_message.connect(self.dashboard.note_log_message)
        w.startup_finished.connect(self._on_startup_finished)
        w.status_recheck_finished.connect(self._refresh_health_badges)

    # ================= ACTIONS =================

    def _on_nav_changed(self, row: int) -> None:
        self.content_stack.setCurrentIndex(row)

    def _on_start_clicked(self) -> None:
        self.start_button.setEnabled(False)
        self.start_button.setText("Starting...")
        self.workers.start()

    def _on_startup_finished(self, success: bool, error: str) -> None:
        if not success:
            # Only a genuinely unexpected failure reaches here now - a
            # CoppeliaSim connection failure is isolated inside
            # start_services() and no longer blocks voice/gesture (see
            # Application.start_services()).
            self.start_button.setText("Start System")
            self.start_button.setEnabled(True)
            for name in ("coppelia", "robot"):
                self.badges[name].set_state("error", error)
            QMessageBox.critical(self, "Startup failed", f"Could not start services:\n{error}")
            return

        self.start_button.setText("Running")
        self._refresh_health_badges()

    def _refresh_health_badges(self) -> None:
        """Drives every header badge (including "whisper" and "ollama",
        which the old ad-hoc per-widget checks below never touched and so
        stayed on their initial "disabled" text forever) from the same
        `health.run_all()` checks the Diagnostics panel uses - one source of
        truth for "is this component actually working" instead of two
        drifting implementations."""
        from src.monitoring import health

        results = {r.name: r for r in health.run_status_checks(self.app)}
        _STATE_FOR_STATUS = {"pass": "ready", "warn": "disabled", "fail": "error"}

        for badge_name, check_name in (
            ("camera", "camera"),
            ("mediapipe", "camera"),  # MediaPipe loads as part of the gesture pipeline - no separate check
            ("microphone", "microphone"),
            ("whisper", "whisper"),
            ("ollama", "ollama"),
            ("coppelia", "coppelia"),
            ("robot", "coppelia"),
        ):
            result = results.get(check_name)
            if result is None:
                continue
            self.badges[badge_name].set_state(_STATE_FOR_STATUS.get(result.status, "disabled"), result.message)

        if results["coppelia"].status != "pass":
            self.log_panel.append_log(
                "WARNING", "coppelia",
                "CoppeliaSim is not connected - robot motion is a no-op. "
                "Voice/gesture recognition are unaffected; start CoppeliaSim and use "
                "\"Reconnect\" in Configuration to retry.",
            )

    def _on_emergency_state_changed(self, active: bool) -> None:
        self.emergency_button.setStyleSheet(
            "background-color: #6b0013; color: white; font-weight: 700; padding: 6px 14px; border: 2px solid yellow;"
            if active
            else "background-color: #b00020; color: white; font-weight: 700; padding: 6px 14px;"
        )

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override naming)
        try:
            self.workers.stop()
        except Exception:
            logger.exception("Error stopping workers on window close")
        event.accept()
