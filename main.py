"""Application entry point.

Responsible only for: parsing CLI arguments, loading and validating
configuration, starting the graphical interface (default) or the headless
loop (`--headless`), and returning an appropriate exit code. All business
logic lives in src/app/application.py and the modules it composes.
"""
import logging
import sys

from src.app.application import Application
from src.app.cli import build_parser
from src.config.loader import ConfigError, load_config


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(preset=args.preset, config_path=args.config)
    except ConfigError as exc:
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        return 1

    if args.log_level:
        config.logging.level = args.log_level.upper()

    app = Application(config)

    try:
        if args.headless:
            return app.run_headless()
        return app.run_gui()
    except KeyboardInterrupt:
        app.stop()
        return 0
    except Exception:
        logging.getLogger("app.main").exception("Fatal startup/runtime error")
        app.stop()
        return 2


if __name__ == "__main__":
    sys.exit(main())
