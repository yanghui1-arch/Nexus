import logging
import os
import sys
from collections import deque


NEXUS_CONFIGURE_LOGGING = int(os.getenv("NEXUS_CONFIGURE_LOGGING", "1"))
NEXUS_LOGGING_LEVEL = os.getenv("NEXUS_LOGGING_LEVEL", "DEBUG")

_FORMAT = "[%(levelname)s %(asctime)s %(filename)s:%(lineno)d] %(message)s"
_DATE_FORMAT = "%m-%d %H:%M:%S"

_LEVEL_COLORS = {
    "DEBUG":    "\033[36m",    # cyan
    "INFO":     "\033[32m",    # green
    "WARNING":  "\033[33m",    # yellow
    "ERROR":    "\033[31m",    # red
    "CRITICAL": "\033[1;31m",  # bold red
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Copy to avoid mutating the shared LogRecord seen by other handlers
        copy = logging.makeLogRecord(record.__dict__)
        color = _LEVEL_COLORS.get(record.levelname, "")
        copy.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(copy)


def _build_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColorFormatter(fmt=_FORMAT, datefmt=_DATE_FORMAT))
    return handler



def init_logger(name: str) -> logging.Logger:
    """Return a named logger with Nexus formatting applied once."""
    log = logging.getLogger(name)
    if NEXUS_CONFIGURE_LOGGING and not log.handlers:
        log.setLevel(NEXUS_LOGGING_LEVEL)
        log.addHandler(_build_handler())
        log.propagate = False
    return log


# Module-level global logger
logger = init_logger("nexus")

