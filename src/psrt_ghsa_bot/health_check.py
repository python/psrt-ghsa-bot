"""Health check script for monitoring GitHub Actions workflows.

TODO: i'd like to know exactly the error and which workflow is failing
  and send it to sentry or slack or an email or whatever
"""

import logging
import os
import sys
from typing import TYPE_CHECKING

from githubkit.exception import RequestFailed

from psrt_ghsa_bot._monitoring import capture_checkin, init_sentry, report_workflow_failure
from psrt_ghsa_bot.settings import settings
from psrt_ghsa_bot.utils.github import get_github_client

if TYPE_CHECKING:
    from githubkit import GitHub

_mon = settings.monitoring

logger = logging.getLogger(__name__)

WORKFLOWS_TO_CHECK = [
    {"file": "cron.yml", "monitor_slug": _mon.MONITOR_SLUG_GHSA},
    {"file": "playwright.yml", "monitor_slug": _mon.MONITOR_SLUG_PLAYWRIGHT},
]


def _get_workflow_runs(github: GitHub, owner: str, repo: str, workflow_file: str) -> list[dict]:
    """Fetch recent workflow runs for a specific workflow file."""
    try:
        response = github.rest.actions.list_workflow_runs(
            owner=owner,
            repo=repo,
            workflow_id=workflow_file,
            per_page=5,
        )
        return [
            {"status": run.status, "conclusion": run.conclusion, "id": run.id}
            for run in response.parsed_data.workflow_runs
        ]
    except RequestFailed as e:
        logger.warning("Failed to get workflow runs: %s", e)
        return []


def check_workflow_health() -> None:
    """Check the health of configured workflows and report to Sentry."""
    github_repository = os.environ.get("GITHUB_REPOSITORY")
    if not github_repository:
        msg = "GITHUB_REPOSITORY environment variable is required"
        raise RuntimeError(msg)

    owner, repo = github_repository.split("/")

    init_sentry()
    capture_checkin(_mon.MONITOR_SLUG_HEALTH, _mon.STATUS_IN_PROGRESS)
    workflow_statuses = {workflow["file"]: False for workflow in WORKFLOWS_TO_CHECK}

    github = get_github_client()
    installations = list(github.rest.paginate(github.rest.apps.list_installations))
    if not installations:
        logger.error("No GitHub App installations found")
        capture_checkin(_mon.MONITOR_SLUG_HEALTH, _mon.STATUS_ERROR)
        sys.exit(1)

    installation_github = github.with_auth(github.auth.as_installation(installations[0].id))

    for workflow in WORKFLOWS_TO_CHECK:
        logger.info("Checking workflow: %s", workflow["file"])

        runs = _get_workflow_runs(installation_github, owner, repo, workflow["file"])

        if not runs:
            logger.warning("No runs found for %s", workflow["file"])
            continue

        completed_runs = [r for r in runs if r["status"] == "completed"]
        if not completed_runs:
            logger.info("No completed runs yet for %s", workflow["file"])
            continue

        latest_run = completed_runs[0]
        conclusion = latest_run["conclusion"]
        run_id = latest_run["id"]
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
