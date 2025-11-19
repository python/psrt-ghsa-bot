"""Health check script for monitoring GitHub Actions workflows.

TODO: i'd like to know exactly the error and which workflow is failing
  and send it to sentry or slack or an email or whatever
"""

import json
import subprocess
import sys

from psrt_ghsa_bot._monitoring import capture_checkin, init_sentry, report_workflow_failure


def check_workflow_health() -> None:
    """Check the health of configured workflows and report to Sentry."""
    init_sentry()

    capture_checkin("psrt-health-monitor", "in_progress")

    workflows_to_check = [
        {"name": "PSRT GHSA Bot", "file": "cron.yml", "monitor_slug": "psrt-ghsa-cron"},
        # {"name": "PSRT Playright Bot", "file": "playwright.yml", "monitor_slug": "psrt-playwright-cron"},
    ]

    all_healthy = True

    for workflow in workflows_to_check:
        print(f"\nChecking workflow: {workflow['name']}")

        """
        This is like:
        ➜ gh run list --workflow cron.yml --json conclusion,status,databaseId --limit 1
        [
          {
            "conclusion": "success",
            "databaseId": 19509767419,
            "status": "completed"
          }
        ]
        """

        result = subprocess.run(
            [
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
            print(f"⚠️  Failed to get workflow runs: {result.stderr}")
            all_healthy = False
            continue

        runs = json.loads(result.stdout)
        if not runs:
            print(f"⚠️  No runs found for {workflow['name']}")
            continue

        completed_runs = [r for r in runs if r["status"] == "completed"]
        if not completed_runs:
            print(f"ℹ️  No completed runs yet for {workflow['name']}")
            continue

        latest_run = completed_runs[0]
        conclusion = latest_run["conclusion"]
        run_id = latest_run["databaseId"]
        print(f"   Latest run: {run_id} - {conclusion}")

        if conclusion in ["failure", "timed_out", "cancelled"]:
            print(f"❌ Workflow failed with status: {conclusion}")
            report_workflow_failure(workflow["name"], str(run_id), conclusion)
            capture_checkin(workflow["monitor_slug"], "error")
            all_healthy = False
        elif conclusion == "success":
            print("✅ Workflow succeeded")
            capture_checkin(workflow["monitor_slug"], "ok")
        else:
            print(f"⚠️  Unexpected conclusion: {conclusion}")
            all_healthy = False

    if all_healthy:
        capture_checkin("psrt-health-monitor", "ok")
        print("\n✅ All workflows healthy")
    else:
        capture_checkin("psrt-health-monitor", "error")
        print("\n❌ Some workflows are unhealthy")
        sys.exit(1)


if __name__ == "__main__":
    check_workflow_health()
