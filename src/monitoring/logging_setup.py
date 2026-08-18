"""Structured logging setup, replacing the codebase's previous print()-based
diagnostics.

Every module should just call `logging.getLogger(__name__-like-string)` and
rely on this having been configured once at startup by `Application`.
"""
import logging
import sys
from typing import Optional

_configured = False


def setup_logging(level: str = "INFO", log_to_file: bool = False, file_path: Optional[str] = None) -> None:
    global _configured
    if _configured:
        return

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_to_file and file_path:
        handlers.append(logging.FileHandler(file_path))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        handlers=handlers,
    )
    _configured = True


def set_level(level: str) -> None:
    """Changes the root logger's level at runtime (e.g. from the
    Configuration panel) without touching handlers/formatting."""
    resolved = getattr(logging, level.upper(), None)
    if resolved is None:
        raise ValueError(f"Unknown log level: {level!r}")
    logging.getLogger().setLevel(resolved)
