"""Health check script for monitoring GitHub Actions workflows.

TODO: i'd like to know exactly the error and which workflow is failing
  and send it to sentry or slack or an email or whatever
"""

import json
import logging
import subprocess
import sys

from psrt_ghsa_bot._monitoring import capture_checkin, init_sentry, report_workflow_failure

logger = logging.getLogger(__name__)


def check_workflow_health() -> None:
    """Check the health of configured workflows and report to Sentry."""
    init_sentry()

    capture_checkin("psrt-health-monitor", "in_progress")

    workflows_to_check = [
        {"name": "PSRT GHSA Bot", "file": "cron.yml", "monitor_slug": "psrt-ghsa-cron"},
        # {"name": "PSRT Playright Bot", "file": "playwright.yml", "monitor_slug": "psrt-playwright-cron"}, # noqa: ERA001, E501
    ]

    all_healthy = True

    for workflow in workflows_to_check:
        logger.info("Checking workflow: %s", workflow["name"])

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
            all_healthy = False
            continue

        runs = json.loads(result.stdout)
        if not runs:
            logger.warning("No runs found for %s", workflow["name"])
            continue

        completed_runs = [r for r in runs if r["status"] == "completed"]
        if not completed_runs:
            logger.info("No completed runs yet for %s", workflow["name"])
            continue

        latest_run = completed_runs[0]
        conclusion = latest_run["conclusion"]
        run_id = latest_run["databaseId"]
        logger.info("Latest run: %s - %s", run_id, conclusion)

        if conclusion in ["failure", "timed_out", "cancelled"]:
            logger.error("Workflow failed with status: %s", conclusion)
            report_workflow_failure(workflow["name"], str(run_id), conclusion)
            capture_checkin(workflow["monitor_slug"], "error")
            all_healthy = False
        elif conclusion == "success":
            logger.info("Workflow succeeded")
            capture_checkin(workflow["monitor_slug"], "ok")
        else:
            logger.warning("Unexpected conclusion: %s", conclusion)
            all_healthy = False

    if all_healthy:
        capture_checkin("psrt-health-monitor", "ok")
        logger.info("All workflows healthy")
    else:
        capture_checkin("psrt-health-monitor", "error")
        logger.error("Some workflows are unhealthy")
        sys.exit(1)


if __name__ == "__main__":
    check_workflow_health()
