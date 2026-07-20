import argparse

PRESET_CHOICES = [
    "low_resource",
    "balanced",
    "high_accuracy",
    "voice_only",
    "gesture_only",
    "multimodal",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Offline multimodal (voice + gesture) robot control.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the console loop instead of opening the graphical interface.",
    )
    parser.add_argument(
        "--preset",
        choices=PRESET_CHOICES,
        default=None,
        help="Named configuration preset layered over the defaults (config/presets/<name>.yaml).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to an additional YAML file layered on top of the defaults/preset.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="Override the configured logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser
