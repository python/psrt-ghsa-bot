"""Sentry cron monitoring integration for the PSRT GHSA bot."""

import os

import sentry_sdk
from sentry_sdk import crons

MONITOR_SLUG_GHSA = "psrt-ghsa-cron"

STATUS_IN_PROGRESS = "in_progress"
STATUS_OK = "ok"
STATUS_ERROR = "error"


def init_sentry() -> None:
    """Initialize the Sentry SDK with the DSN from the env"""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        enable_tracing=False,
    )


def capture_checkin(monitor_slug, status, duration=None, check_in_id=None):
    """Capture a Sentry cron check-in."""
    if not os.environ.get("SENTRY_DSN"):
        return None

    try:
        return crons.capture_checkin(
            monitor_slug=monitor_slug,
            status=status,
            duration=duration,
            check_in_id=check_in_id,
        )
    except ImportError, AttributeError:
        return None
