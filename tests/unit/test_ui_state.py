from src.ui.state import AppState, CommandUIState, ComponentStatus, GestureUIState, VoiceUIState


def test_app_state_constructs_with_defaults():
    state = AppState()
    assert state.voice.listening is False
    assert state.gesture.gesture is None
    assert state.command.status == "none"
    assert state.emergency_stop_active is False


def test_app_state_is_a_plain_snapshot_not_a_shared_mutable_object():
    first = AppState(fusion_mode="voice_priority")
    second = AppState(fusion_mode="combined")
    assert first.fusion_mode == "voice_priority"
    assert second.fusion_mode == "combined"


def test_component_status_requires_a_known_state():
    status = ComponentStatus(name="whisper", state="ready", message="Model loaded")
    assert status.state == "ready"


def test_voice_and_gesture_ui_state_defaults_are_idle():
    voice = VoiceUIState()
    gesture = GestureUIState()
    assert voice.processing_state == "idle"
    assert gesture.state == "idle"


def test_command_ui_state_defaults_to_no_status():
    command = CommandUIState()
    assert command.status == "none"
    assert command.action is None
