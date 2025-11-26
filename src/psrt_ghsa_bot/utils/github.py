"""GitHub client utilities."""

import base64
import logging
from typing import TYPE_CHECKING, Any

from githubkit import AppAuthStrategy, GitHub
from githubkit.exception import RequestFailed

from psrt_ghsa_bot.settings import settings

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


type InstallationRepo = tuple[GitHub, Any]


def get_github_client() -> GitHub:
    """Create GitHub client authenticated as the GitHub App."""
    private_key = base64.b64decode(settings.github.GH_CLIENT_PRIVATE_KEY).decode().strip()
    return GitHub(AppAuthStrategy(settings.github.GH_CLIENT_ID, private_key))


def get_workflow_runs(
    github: GitHub,
    owner: str,
    repo: str,
    workflow_file: str,
    per_page: int = 5,
) -> list[dict]:
    """Fetch recent workflow runs for a specific workflow file.

    Args:
        github: Authenticated GitHub client
        owner: Repository owner
        repo: Repository name
        workflow_file: Workflow filename (e.g., "cron.yml")
        per_page: Number of runs to fetch (default 5)

    Returns:
        List of workflow run dicts with status, conclusion, and id
    """
    try:
        response = github.rest.actions.list_workflow_runs(
            owner=owner,
            repo=repo,
            workflow_id=workflow_file,
            per_page=per_page,
        )
        return [
            {"status": run.status, "conclusion": run.conclusion, "id": run.id}
            for run in response.parsed_data.workflow_runs
        ]
    except RequestFailed as e:
        logger.warning("Failed to get workflow runs: %s", e)
        return []


def iter_installation_repos(github: GitHub) -> Iterator[InstallationRepo]:
    """Iterate over all repos across all GitHub App installations.

    Yields:
        Tuple of (installation_github, repo) where installation_github is
        an authenticated client scoped to the installation, and repo is
        the repository object.
    """
    installations = github.rest.paginate(github.rest.apps.list_installations)
    for installation_data in installations:
        installation_github = github.with_auth(
            github.auth.as_installation(installation_data.id),
        )
        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )
        for repo in repos:
            yield installation_github, repo
