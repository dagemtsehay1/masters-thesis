import pytest

from src.config.loader import ConfigError, load_config
from src.config.schema import AppConfig


def test_load_default_config_is_valid():
    config = load_config()
    assert isinstance(config, AppConfig)
    assert config.fusion.mode == "voice_priority"
    assert config.gesture.enabled is True
    assert config.voice.enabled is True


@pytest.mark.parametrize(
    "preset,voice_enabled,gesture_enabled",
    [
        ("voice_only", True, False),
        ("gesture_only", False, True),
        ("multimodal", True, True),
    ],
)
def test_presets_toggle_modalities(preset, voice_enabled, gesture_enabled):
    config = load_config(preset=preset)
    assert config.voice.enabled is voice_enabled
    assert config.gesture.enabled is gesture_enabled


def test_low_resource_preset_reduces_camera_and_logging():
    config = load_config(preset="low_resource")
    assert config.camera.resolution == (320, 240)
    assert config.logging.level == "WARNING"


def test_balanced_preset_matches_defaults():
    default = load_config()
    balanced = load_config(preset="balanced")
    # Everything matches the defaults except the informational marker of
    # which preset was loaded (set by load_config itself, not the file).
    assert balanced.general.active_preset == "balanced"
    balanced.general.active_preset = None
    assert balanced == default


def test_unknown_preset_raises_config_error():
    with pytest.raises(ConfigError):
        load_config(preset="does_not_exist")


def test_extra_field_is_rejected(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("robot:\n  not_a_real_field: 123\n")
    with pytest.raises(ConfigError):
        load_config(config_path=str(bad_config))


def test_invalid_fusion_mode_is_rejected(tmp_path):
    bad_config = tmp_path / "bad_fusion.yaml"
    bad_config.write_text("fusion:\n  mode: not_a_real_mode\n")
    with pytest.raises(ConfigError):
        load_config(config_path=str(bad_config))


@pytest.mark.parametrize(
    "preset,expected_mode",
    [("voice_only", "voice_only"), ("gesture_only", "gesture_only"), ("multimodal", "combined")],
)
def test_presets_set_expected_fusion_mode(preset, expected_mode):
    config = load_config(preset=preset)
    assert config.fusion.mode == expected_mode


def test_env_var_overrides_coppelia_host(monkeypatch):
    monkeypatch.setenv("APP_COPPELIA_HOST", "192.168.1.50")
    monkeypatch.setenv("APP_COPPELIA_PORT", "9999")
    config = load_config()
    assert config.coppelia.host == "192.168.1.50"
    assert config.coppelia.port == 9999
