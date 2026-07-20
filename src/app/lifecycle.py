"""Startup/shutdown plumbing for the Application.

Kept deliberately small: it answers "how do we shut down cleanly", it does
not own any business logic itself.
"""
import logging
import signal

logger = logging.getLogger("app.lifecycle")


def install_shutdown_handler(on_shutdown) -> None:
    """Install a SIGTERM handler that runs `on_shutdown`.

    SIGINT is left untouched so Ctrl+C keeps raising KeyboardInterrupt,
    which the headless loop already handles explicitly.
    """

    def _handler(signum, frame):
        logger.info("Received SIGTERM, shutting down...")
        on_shutdown()

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, AttributeError, OSError):
        # Not available on this platform/thread context (e.g. not the main
        # thread, or an OS without SIGTERM semantics) - non-fatal.
        logger.debug("SIGTERM handler not installed on this platform")
