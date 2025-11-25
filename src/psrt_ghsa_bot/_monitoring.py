"""Sentry cron monitoring integration for GH act workflows."""

import os
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk import crons

from psrt_ghsa_bot.settings import settings

if TYPE_CHECKING:
    from psrt_ghsa_bot.config import CheckinStatus


def init_sentry() -> None:
    """Initialize Sentry SDK with DSN from envvars."""
    dsn = settings.monitoring.SENTRY_DSN
    if not dsn:
        return

    sentry_sdk.init(
        dsn=dsn,
        enable_tracing=False,
    )


def capture_checkin(
    monitor_slug: str,
    status: CheckinStatus,
    duration: float | None = None,
) -> str | None:
    """Capture a Sentry cron check-in.

    Args:
        monitor_slug: The unique identifier for this monitor (e.g., "psrt-ghsa-cron")
        status: The status of the check-in (STATUS_IN_PROGRESS, STATUS_OK, or STATUS_ERROR)
        duration: Optional duration in seconds for the job execution

    Returns:
        Check-in ID if successful else none
    """
    if not settings.monitoring.SENTRY_DSN:
        return None

    try:
        return crons.capture_checkin(
            monitor_slug=monitor_slug,
            status=status,
            duration=duration,
        )
    except (ImportError, AttributeError):
        return None


def report_workflow_failure(workflow_name: str, run_id: str, conclusion: str) -> None:
    """Report a workflow failure to Sentry as an error event.

    This is used by the health check workflow (health-chcek.yml) to report when other workflows fail.
    We want to check status of our playright actions and our cron.yml action to make sure they are
    running and since they arent running constantly on some web service anywhere this is the idea..

    Args:
        workflow_name: Name of the failed workflow
        run_id: GitHub Actions run ID
        conclusion: The conclusion status from GitHub Actions

    Raises:
        RuntimeError: If GITHUB_REPOSITORY environment variable is not set
    """
    if not settings.monitoring.SENTRY_DSN:
        return

    github_repository = os.environ.get("GITHUB_REPOSITORY")
    if not github_repository:
        msg = "GITHUB_REPOSITORY environment variable is required"
        raise RuntimeError(msg)

    sentry_sdk.capture_message(
        f"Workflow '{workflow_name}' failed with status: {conclusion}",
        level="error",
        extras={
            "workflow_name": workflow_name,
            "run_id": run_id,
            "conclusion": conclusion,
            "workflow_url": f"https://github.com/{github_repository}/actions/runs/{run_id}",
        },
    )
