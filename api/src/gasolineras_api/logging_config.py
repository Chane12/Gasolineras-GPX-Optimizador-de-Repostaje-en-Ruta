"""Logging for the running API (uvicorn only configures its own loggers, so ours were silent)."""

import logging
import os

LOG_LEVEL_ENV = "GASOLINERAS_LOG_LEVEL"
_OUR_LOGGERS = ("gasolineras_api", "gasolineras_core")


def configure_logging() -> None:
    """Send our loggers to stderr (Cloud Run collects it). Idempotent; level from GASOLINERAS_LOG_LEVEL."""
    level = os.environ.get(LOG_LEVEL_ENV, "INFO").upper()
    for name in _OUR_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            logger.addHandler(handler)
        logger.propagate = False
