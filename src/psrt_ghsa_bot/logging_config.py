"""Centralized logging configuration for PSRT GHSA Bot."""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging for entire app.

    Args:
        level: Logging level (default: INFO)
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("psrt-ghsa-bot.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # set these higher so they arent noiys..
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("githubkit").setLevel(logging.WARNING)
