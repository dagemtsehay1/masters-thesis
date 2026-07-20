"""Background workers bridging services to the UI thread.

Three QThread-backed workers, each independently paced:
  - VoiceWorker: loops on `VoicePipeline.poll()` (audio capture + VAD +
    Whisper transcription + intent resolution, all off the UI thread).
  - GestureWorker: loops on `GesturePipeline.poll()` (camera capture is
    already decoupled inside the pipeline itself - this just keeps
    inference off the UI thread too).
  - RobotWorker: ticks fusion + `RobotController.step()` on a QTimer so it
    stays responsive to queued cross-thread requests (manual commands,
    emergency stop) while it runs - unlike the other two, which never need
    to *receive* calls mid-loop, so a plain blocking loop is fine for them.

All three only ever emit UI-state snapshots (src/ui/state.py) or log
lines - they hold no reference to any Qt widget, and no widget calls back
into a service directly. Voice and gesture events are handed to the robot
worker through a tiny lock-protected holder (`_SharedEvents`), the same
safe cross-thread pattern the old Tkinter GUI used for voice alone.
"""
import logging
import threading
import time
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot

from src.ui.state import CommandUIState, GestureUIState, VoiceUIState

logger = logging.getLogger("ui.workers")


class _SharedEvents:
    def __init__(self):
        self._lock = threading.Lock()
        self._voice_event = None
        self._gesture_event = None

    def set_voice(self, event) -> None:
        with self._lock:
            self._voice_event = event

    def set_gesture(self, event) -> None:
        with self._lock:
            self._gesture_event = event

    def snapshot(self):
        with self._lock:
            return self._voice_event, self._gesture_event


class VoiceWorker(QObject):
    state_changed = Signal(object)  # VoiceUIState
    waveform_ready = Signal(object)  # np.ndarray of samples
    log_message = Signal(str, str, str)  # level, component, message

    def __init__(self, application, shared_events: _SharedEvents):
        super().__init__()
        self._app = application
        self._shared = shared_events
        self._running = False

    def run_loop(self) -> None:
        self._running = True
        voice = self._app.voice
        if voice is None:
            return

        while self._running:
            try:
                event, waveform = voice.poll(chunk_timeout_s=0.05)
            except Exception:
                logger.exception("voice.poll() failed")
                self.state_changed.emit(VoiceUIState(processing_state="error"))
                time.sleep(0.2)
                continue

            if waveform is not None:
                self.waveform_ready.emit(waveform)

            if event is not None and event.command is not None:
                self._shared.set_voice(event)
                self.state_changed.emit(
                    VoiceUIState(
                        listening=True,
                        speech_detected=True,
                        language=event.language,
                        transcript=event.command,
                        normalized_text=event.command,
                        confidence=event.confidence,
                        processing_state="complete",
                    )
                )
                self.log_message.emit("INFO", "voice", f"Recognized command: {event.command}")
            else:
                self.state_changed.emit(VoiceUIState(listening=True, processing_state="listening"))

    def stop(self) -> None:
        self._running = False


class GestureWorker(QObject):
    state_changed = Signal(object)  # GestureUIState
    frame_ready = Signal(object)  # np.ndarray | None
    log_message = Signal(str, str, str)

    def __init__(self, application, shared_events: _SharedEvents):
        super().__init__()
        self._app = application
        self._shared = shared_events
        self._running = False

    def run_loop(self) -> None:
        self._running = True
        pipeline = self._app.gesture
        if pipeline is None:
            return

        while self._running:
            try:
                poll_start = time.perf_counter()
                event, frame = pipeline.poll()
                self._app.metrics.record_latency("gesture", (time.perf_counter() - poll_start) * 1000)
            except Exception:
                logger.exception("gesture.poll() failed")
                time.sleep(0.1)
                continue

            if event is not None:
                self._shared.set_gesture(event)
                self.state_changed.emit(
                    GestureUIState(
                        camera_active=True,
                        hand_detected=event.gesture is not None,
                        handedness=event.hand,
                        gesture=event.gesture,
                        confidence=event.confidence,
                        state=event.state,
                        confirmation_progress=pipeline.smoother.confirmation_progress,
                        confirmation_required=pipeline.smoother.confirmation_required,
                    )
                )
                if event.state == "confirmed":
                    self.log_message.emit("INFO", "gesture", f"Confirmed: {event.gesture}")

            if frame is not None:
                self.frame_ready.emit(frame)

            time.sleep(0.01)

    def stop(self) -> None:
        self._running = False


class RobotWorker(QObject):
    services_ready = Signal(bool, str)
    command_state_changed = Signal(object)  # CommandUIState
    robot_state_changed = Signal(str, str)  # controller.state, controller.mode
    emergency_state_changed = Signal(bool)
    log_message = Signal(str, str, str)

    def __init__(self, application, shared_events: _SharedEvents, tick_interval_ms: int = 50):
        super().__init__()
        self._app = application
        self._shared = shared_events
        self._tick_interval_ms = tick_interval_ms
        self._timer: Optional[QTimer] = None

    @Slot()
    def start(self) -> None:
        try:
            self._app.start_services()
        except Exception as exc:
            logger.exception("start_services() failed")
            self.services_ready.emit(False, str(exc))
            return

        self.services_ready.emit(True, "")
        self._timer = QTimer(self)
        self._timer.setInterval(self._tick_interval_ms)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    @Slot()
    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    def _tick(self) -> None:
        try:
            voice_event, gesture_event = self._shared.snapshot()
            decision = self._app.fusion.resolve(voice_event, gesture_event)

            command_state = CommandUIState()
            if decision is not None:
                command_state.source = decision.command.source
                command_state.action = decision.command.action
                command_state.direction = decision.command.direction
                command_state.confidence = decision.command.confidence

                result = self._app.submit_fusion_decision(decision)
                if result is not None:
                    command_state.status = "validated"
                    self._app.metrics.increment("commands_executed")
                    self.log_message.emit(
                        "INFO", "fusion", f"{decision.command.action}/{decision.command.direction} ({decision.reason})"
                    )
                else:
                    command_state.status = "rejected"
                    command_state.rejection_reason = "rejected by validator/safety"
                    self._app.metrics.increment("commands_rejected")

            self.command_state_changed.emit(command_state)

            self._app.controller.step()
            self.robot_state_changed.emit(self._app.controller.state, self._app.controller.mode)
            self.emergency_state_changed.emit(self._app.safety.emergency_stop_active)
        except Exception:
            logger.exception("Error in RobotWorker tick")

    @Slot(str)
    def request_manual_command(self, command_word: str) -> None:
        self._app.submit_command(command_word, source="manual")

    @Slot()
    def request_emergency_stop(self) -> None:
        self._app.safety.trigger_emergency_stop(reason="UI emergency button")

    @Slot()
    def request_resume(self) -> None:
        self._app.safety.clear_emergency_stop()


class ServiceWorkers(QObject):
    """Owns the three threads above and re-exposes their signals under one
    object so `main_window.py` doesn't need to know about thread plumbing."""

    startup_finished = Signal(bool, str)
    voice_state_changed = Signal(object)
    waveform_ready = Signal(object)
    gesture_state_changed = Signal(object)
    frame_ready = Signal(object)
    command_state_changed = Signal(object)
    robot_state_changed = Signal(str, str)
    emergency_state_changed = Signal(bool)
    log_message = Signal(str, str, str)

    # Outgoing requests to RobotWorker - real signals (not direct method
    # calls) so Qt delivers them via a queued connection onto the robot
    # thread instead of racing its QTimer from the UI thread.
    manual_command_requested = Signal(str)
    emergency_stop_requested = Signal()
    resume_requested = Signal()

    def __init__(self, application):
        super().__init__()
        self.app = application
        self._shared = _SharedEvents()

        self._voice_thread = QThread()
        self._gesture_thread = QThread()
        self._robot_thread = QThread()

        self.voice_worker = VoiceWorker(application, self._shared)
        self.gesture_worker = GestureWorker(application, self._shared)
        self.robot_worker = RobotWorker(application, self._shared)

        self.voice_worker.moveToThread(self._voice_thread)
        self.gesture_worker.moveToThread(self._gesture_thread)
        self.robot_worker.moveToThread(self._robot_thread)

        self.voice_worker.state_changed.connect(self.voice_state_changed)
        self.voice_worker.waveform_ready.connect(self.waveform_ready)
        self.voice_worker.log_message.connect(self.log_message)
        self.gesture_worker.state_changed.connect(self.gesture_state_changed)
        self.gesture_worker.frame_ready.connect(self.frame_ready)
        self.gesture_worker.log_message.connect(self.log_message)
        self.robot_worker.command_state_changed.connect(self.command_state_changed)
        self.robot_worker.robot_state_changed.connect(self.robot_state_changed)
        self.robot_worker.emergency_state_changed.connect(self.emergency_state_changed)
        self.robot_worker.log_message.connect(self.log_message)
        self.robot_worker.services_ready.connect(self._on_services_ready)

        self.manual_command_requested.connect(self.robot_worker.request_manual_command)
        self.emergency_stop_requested.connect(self.robot_worker.request_emergency_stop)
        self.resume_requested.connect(self.robot_worker.request_resume)

        self._robot_thread.started.connect(self.robot_worker.start)
        self._voice_thread.started.connect(self.voice_worker.run_loop)
        self._gesture_thread.started.connect(self.gesture_worker.run_loop)

    def start(self) -> None:
        self._robot_thread.start()

    def _on_services_ready(self, success: bool, error: str) -> None:
        self.startup_finished.emit(success, error)
        if not success:
            return
        if self.app.voice is not None:
            self._voice_thread.start()
        if self.app.gesture is not None:
            self._gesture_thread.start()

    def submit_manual_command(self, command_word: str) -> None:
        self.manual_command_requested.emit(command_word)

    def trigger_emergency_stop(self) -> None:
        self.emergency_stop_requested.emit()

    def clear_emergency_stop(self) -> None:
        self.resume_requested.emit()

    def stop(self) -> None:
        # VoiceWorker/GestureWorker just run plain while-loops (no QTimer),
        # so flipping their flag directly is fine. RobotWorker owns a
        # QTimer, which Qt requires only ever be touched from its own
        # thread - stop it via a queued call instead of reaching across
        # threads directly.
        self.voice_worker.stop()
        self.gesture_worker.stop()
        QMetaObject.invokeMethod(self.robot_worker, "stop", Qt.ConnectionType.QueuedConnection)

        for thread in (self._voice_thread, self._gesture_thread, self._robot_thread):
            thread.quit()
            thread.wait(2000)

        self.app.stop()
