"""Owns the application's lifecycle: constructing services from config,
running either the headless loop or the GUI, and shutting everything down
the same way regardless of which one was used. `main.py` should never do
more than hand off to this module.
"""
import logging
import time

from src.app.lifecycle import install_shutdown_handler
from src.audio.capture import AudioCapture
from src.audio.vad import VoiceActivityDetector
from src.commands.adapters import command_from_legacy_string
from src.commands.validator import CommandValidator
from src.config.schema import AppConfig
from src.fusion.engine import FusionEngine
from src.gesture.pipeline import GesturePipeline
from src.intent.intent_engine import IntentEngine
from src.intent.qwen_client import QwenClient
from src.monitoring.logging_setup import setup_logging
from src.monitoring.metrics import MetricsCollector
from src.robot.controller import RobotController
from src.robot.coppelia_client import CoppeliaClient
from src.robot.safety import SafetyController
from src.speech.pipeline import VoicePipeline
from src.speech.transcriber import WhisperTranscriber

logger = logging.getLogger("app.application")


class Application:
    """Shared services (config, safety, validator, fusion) plus whichever
    hardware/model components the running mode needs.

    Both `run_headless()` and the GUI's `RobotWorker` (src/ui/workers.py)
    call `start_services()` to build the client/controller/detectors - the
    GUI just does it on a background thread instead of the process's main
    thread, so a slow CoppeliaSim connection or model load never blocks the
    UI. `stop()` is the single cleanup path either mode ends up calling.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        setup_logging(
            level=config.logging.level,
            log_to_file=config.logging.log_to_file,
            file_path=config.logging.file_path,
        )

        self.safety = SafetyController(config.safety)
        self.validator = CommandValidator(config.robot, config.safety)
        self.fusion = FusionEngine(config.fusion, speech_config=config.speech)
        self.metrics = MetricsCollector(history_size=config.ui.chart_history_samples)

        self.client = None
        self.controller = None
        self.voice = None
        self.gesture = None
        self.qwen_client = None  # populated in start_services() if intent.qwen.enabled (Phase 6)

        self._running = False
        self._stopped = False

        install_shutdown_handler(self.stop)

    # ================= LIFECYCLE =================

    def start_services(self) -> None:
        """Builds the CoppeliaSim connection, robot controller, and the
        enabled detectors. Called by `run_headless()` directly, and by
        `src.ui.workers.RobotWorker.start()` on its own thread for the GUI.

        The three subsystems below (CoppeliaSim, voice, gesture) are
        deliberately isolated from one another: a CoppeliaSim connection
        failure must not prevent Whisper/MediaPipe from loading, and a
        voice-init failure (e.g. no microphone) must not prevent gesture
        from starting, and vice versa - matching the architecture's
        "perception must be testable without robot motion" principle and
        "voice and gesture channels remain independent". Each subsystem
        that fails to start is logged clearly and left as `None`/
        disconnected rather than aborting the other two.
        """
        logger.info("Connecting to CoppeliaSim...")
        try:
            self.client = CoppeliaClient(
                host=self.config.coppelia.host,
                port=self.config.coppelia.port,
                robot_object=self.config.coppelia.robot_object,
                retry_attempts=self.config.coppelia.connect_retry_attempts,
                retry_delay_s=self.config.coppelia.connect_retry_delay_s,
            )
        except Exception:
            # CoppeliaClient.connect() itself doesn't raise on connection
            # failure (see its docstring) - this only catches a genuinely
            # unexpected construction error, so the client still exists in
            # a disconnected state and voice/gesture can proceed.
            logger.exception("Unexpected error constructing CoppeliaClient - continuing without it")
            self.client = None
        self.controller = RobotController(self.client, self.safety, self.config.robot)

        try:
            # Always constructed (it does nothing until `.enabled` is true -
            # see QwenClient.enabled) so the Configuration panel can flip
            # `intent.qwen.enabled` on live, later in the session, without
            # needing the voice pipeline restarted.
            self.qwen_client = QwenClient(self.config.intent.qwen)
            if self.config.intent.qwen.enabled:
                if self.qwen_client.health_check():
                    logger.info("Ollama/Qwen fallback available (model=%s)", self.config.intent.qwen.model)
                else:
                    logger.warning("Ollama/Qwen enabled but not reachable - fallback tier will be inactive")
            else:
                logger.info("Qwen intent fallback disabled by configuration")
        except Exception:
            logger.exception("Failed to initialize Qwen client - fallback tier disabled")
            self.qwen_client = None

        if self.config.voice.enabled:
            try:
                logger.info("Loading Whisper model '%s'...", self.config.speech.whisper.model)
                speech_cfg = self.config.speech
                audio = AudioCapture(
                    sample_rate=self.config.microphone.sample_rate,
                    device_index=self.config.microphone.device_index,
                )
                vad = VoiceActivityDetector(
                    sample_rate=self.config.microphone.sample_rate,
                    frame_ms=speech_cfg.vad.frame_ms,
                    silence_timeout_s=speech_cfg.vad.silence_timeout_s,
                    max_recording_s=speech_cfg.vad.max_recording_s,
                    aggressiveness=speech_cfg.vad.aggressiveness,
                    backend=speech_cfg.vad.backend,
                )
                # `languages.mode` is the single knob that decides whether
                # Whisper and intent resolution are bilingual or locked to
                # one language:
                #   - "auto": Whisper detects the spoken language itself
                #     (pinned_language=None) and both alias tables from
                #     `languages.enabled` stay loaded, matching whichever
                #     language Whisper reports per utterance.
                #   - "en"/"am": Whisper is forced to decode in that
                #     language only (it will never report the other one, so
                #     it can't transcribe Amharic speech as English words or
                #     vice versa), and IntentEngine is restricted to that
                #     language's alias table too - even if `languages.enabled`
                #     lists both, the other one is never reachable while a
                #     specific mode is pinned.
                if speech_cfg.languages.mode == "auto":
                    pinned_language = None
                    enabled_languages = speech_cfg.languages.enabled
                    default_language = speech_cfg.languages.default_language
                else:
                    pinned_language = speech_cfg.languages.mode
                    enabled_languages = [speech_cfg.languages.mode]
                    default_language = speech_cfg.languages.mode

                transcriber = WhisperTranscriber(
                    model_size=speech_cfg.whisper.model,
                    device=speech_cfg.whisper.device,
                    compute_type=speech_cfg.whisper.compute_type,
                    pinned_language=pinned_language,
                )
                intent_engine = IntentEngine(
                    language=default_language,
                    enabled_languages=enabled_languages,
                    confidence_threshold=speech_cfg.confidence_threshold,
                    qwen_client=self.qwen_client,
                )
                self.voice = VoicePipeline(audio, vad, transcriber, intent_engine)
                self.voice.start()
            except Exception:
                logger.exception("Failed to start the voice pipeline - voice recognition disabled for this run")
                self.voice = None
        else:
            logger.info("Voice pipeline disabled by configuration")

        if self.config.gesture.enabled:
            try:
                logger.info("Loading gesture pipeline...")
                self.gesture = GesturePipeline(self.config.camera, self.config.gesture)
                self.gesture.start()
            except Exception:
                logger.exception("Failed to start the gesture pipeline - gesture recognition disabled for this run")
                self.gesture = None
        else:
            logger.info("Gesture pipeline disabled by configuration")

        logger.info(
            "Startup complete. voice=%s gesture=%s coppelia=%s",
            "enabled" if self.voice else "disabled",
            "enabled" if self.gesture else "disabled",
            "connected" if (self.client and self.client.is_connected()) else "disconnected",
        )

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._running = False
        logger.info("Shutting down...")

        # Force the robot to a stop regardless of what state it thought it
        # was in - this must not depend on any of the components below.
        self.safety.trigger_emergency_stop(reason="application shutdown")
        if self.controller is not None:
            try:
                self.controller._stop_robot()
            except Exception:
                logger.exception("Error stopping robot during shutdown")

        if self.gesture is not None:
            try:
                self.gesture.stop()
            except Exception:
                logger.exception("Error stopping gesture detector during shutdown")

        if self.voice is not None:
            try:
                self.voice.stop()
            except Exception:
                logger.exception("Error stopping voice pipeline during shutdown")

    def submit_command(self, raw_command: str, source: str, confidence: float = 1.0):
        """Turns a legacy string command into a validated RobotCommand and
        executes it, or returns None if it was rejected. Used for manual/
        direct submissions (e.g. a UI robot-control panel) that bypass
        fusion entirely - fused voice+gesture commands go through
        `submit_fusion_decision` instead."""
        candidate = command_from_legacy_string(raw_command, source=source, confidence=confidence)
        if candidate is None:
            return None
        return self._validate_and_execute(candidate)

    def submit_fusion_decision(self, decision):
        """Validates and executes a `FusionDecision` from `self.fusion`, or
        returns None if it was rejected (or if there was no decision)."""
        if decision is None:
            return None
        return self._validate_and_execute(decision.command)

    def _validate_and_execute(self, candidate):
        result = self.validator.validate(candidate)
        if not result.accepted:
            logger.info("Rejected command %s/%s from %s: %s", candidate.action, candidate.direction, candidate.source, result.reason)
            return None

        self.controller.handle_command(result.command)
        return result.command

    # ================= HEADLESS LOOP =================

    def run_headless(self) -> int:
        self.start_services()
        logger.info("System started (headless). fusion_mode=%s", self.config.fusion.mode)

        self._running = True
        try:
            while self._running:
                try:
                    voice_event = None
                    if self.voice:
                        # Small timeout so this doesn't dominate the loop's
                        # ~50ms tick pacing the way blocking on a full audio
                        # chunk (up to the default 0.05s) would on top of
                        # the sleep below.
                        voice_event, _waveform = self.voice.poll(chunk_timeout_s=0.01)

                    gesture_event = None
                    if self.gesture:
                        gesture_event, _frame = self.gesture.poll()

                    decision = self.fusion.resolve(voice_event, gesture_event)
                    if decision:
                        logger.info(
                            "Fusion decision: %s/%s (source=%s, %s)",
                            decision.command.action,
                            decision.command.direction,
                            decision.command.source,
                            decision.reason,
                        )
                        self.submit_fusion_decision(decision)

                    self.controller.step()
                    time.sleep(0.05)

                except KeyboardInterrupt:
                    logger.info("Stopping (KeyboardInterrupt)...")
                    break
                except Exception:
                    logger.exception("Error in main loop")
                    self.safety.trigger_emergency_stop(reason="unhandled loop error")
                    self.controller.step()
        finally:
            self.stop()

        return 0

    # ================= GUI =================

    def run_gui(self) -> int:
        from PySide6.QtGui import QColor, QPalette
        from PySide6.QtWidgets import QApplication

        from src.ui.main_window import MainWindow

        qt_app = QApplication.instance() or QApplication([])

        # Force a light theme regardless of the OS/system color scheme.
        qt_app.setStyle("Fusion")
        light_palette = QPalette()
        light_palette.setColor(QPalette.Window, QColor("#f5f5f5"))
        light_palette.setColor(QPalette.WindowText, QColor("#202020"))
        light_palette.setColor(QPalette.Base, QColor("#ffffff"))
        light_palette.setColor(QPalette.AlternateBase, QColor("#f0f0f0"))
        light_palette.setColor(QPalette.ToolTipBase, QColor("#ffffff"))
        light_palette.setColor(QPalette.ToolTipText, QColor("#202020"))
        light_palette.setColor(QPalette.Text, QColor("#202020"))
        light_palette.setColor(QPalette.Button, QColor("#f0f0f0"))
        light_palette.setColor(QPalette.ButtonText, QColor("#202020"))
        light_palette.setColor(QPalette.BrightText, QColor("#ff0000"))
        light_palette.setColor(QPalette.Highlight, QColor("#1971c2"))
        light_palette.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        light_palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#a0a0a0"))
        light_palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#a0a0a0"))
        light_palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#a0a0a0"))
        qt_app.setPalette(light_palette)

        window = MainWindow(self)
        window.show()
        return qt_app.exec()
