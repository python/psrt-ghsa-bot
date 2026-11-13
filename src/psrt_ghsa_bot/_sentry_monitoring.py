"""Sentry cron monitoring integration for the PSRT GHSA bot."""

import contextlib
import os
import time

import sentry_sdk
from sentry_sdk import crons

MONITOR_SLUG_GHSA = "psrt-ghsa-cron"

STATUS_IN_PROGRESS = "in_progress"
STATUS_OK = "ok"
STATUS_ERROR = "error"


def init_sentry() -> None:
    """Initialize the Sentry SDK with the DSN from the env"""
    if dsn := os.environ.get("SENTRY_DSN"):
        print("Initializing Sentry monitoring")
    else:
        print("No SENTRY_DSN set, skipping Sentry monitoring")
    sentry_sdk.init(
        dsn=dsn,
        enable_tracing=False,
    )


@contextlib.contextmanager
def cron():
    start_time = time.monotonic()
    try:
        check_in_id = crons.capture_checkin(
            monitor_slug=MONITOR_SLUG_GHSA,
            status=STATUS_IN_PROGRESS,
        )
    except ImportError, AttributeError:
        check_in_id = None
    try:
        yield
    except Exception:
        sentry_sdk.capture_exception()
        status = STATUS_ERROR
        raise
    else:
        status = STATUS_OK
    finally:
        if check_in_id is not None:
            crons.capture_checkin(
                monitor_slug=MONITOR_SLUG_GHSA,
                status=status,
                duration=time.monotonic() - start_time,
                check_in_id=check_in_id,
            )
