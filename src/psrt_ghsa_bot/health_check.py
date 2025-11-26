"""Health check script for monitoring GitHub Actions workflows.

TODO: i'd like to know exactly the error and which workflow is failing
  and send it to sentry or slack or an email or whatever
"""

import json
import logging
import subprocess
import sys

from psrt_ghsa_bot._monitoring import capture_checkin, init_sentry, report_workflow_failure
from psrt_ghsa_bot.settings import settings

_mon = settings.monitoring

logger = logging.getLogger(__name__)

WORKFLOWS_TO_CHECK = [
    {"file": "cron.yml", "monitor_slug": _mon.MONITOR_SLUG_GHSA},
    {"file": "playwright.yml", "monitor_slug": _mon.MONITOR_SLUG_PLAYWRIGHT},
]


def check_workflow_health() -> None:
    """Check the health of configured workflows and report to Sentry."""
    init_sentry()
    capture_checkin(_mon.MONITOR_SLUG_HEALTH, _mon.STATUS_IN_PROGRESS)
    workflow_statuses = {workflow["file"]: False for workflow in WORKFLOWS_TO_CHECK}

    for workflow in WORKFLOWS_TO_CHECK:
        logger.info("Checking workflow: %s", workflow["file"])

        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "gh",
                "run",
                "list",
                "--workflow",
                workflow["file"],
                "--json",
                "conclusion,status,databaseId",
                "--limit",
                "5",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning("Failed to get workflow runs: %s", result.stderr)
            continue

        try:
            runs = json.loads(result.stdout)
        except ValueError:
            logger.warning("Failed to parse workflow runs for %s", workflow["file"])
            continue

        if not runs:
            logger.warning("No runs found for %s", workflow["file"])
            continue

        completed_runs = [r for r in runs if r["status"] == "completed"]
        if not completed_runs:
            logger.info("No completed runs yet for %s", workflow["file"])
            continue

        latest_run = completed_runs[0]
        conclusion = latest_run["conclusion"]
        run_id = latest_run["databaseId"]
        logger.info("Latest run: %s - %s", run_id, conclusion)

        if conclusion in ["failure", "timed_out", "cancelled"]:
            logger.error("Workflow failed with status: %s", conclusion)
            report_workflow_failure(workflow["file"], str(run_id), conclusion)
            capture_checkin(workflow["monitor_slug"], _mon.STATUS_ERROR)
        elif conclusion == "success":
            logger.info("Workflow succeeded")
            capture_checkin(workflow["monitor_slug"], _mon.STATUS_OK)
            workflow_statuses[workflow["file"]] = True
        else:
            logger.warning("Unexpected conclusion: %s", conclusion)

    if all(workflow_statuses.values()):
        capture_checkin(_mon.MONITOR_SLUG_HEALTH, _mon.STATUS_OK)
        logger.info("All workflows healthy")
    else:
        capture_checkin(_mon.MONITOR_SLUG_HEALTH, _mon.STATUS_ERROR)
        logger.error("Some workflows are unhealthy")
        sys.exit(1)


if __name__ == "__main__":
    check_workflow_health()
