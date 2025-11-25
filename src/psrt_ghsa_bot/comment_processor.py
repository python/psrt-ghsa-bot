"""Comment processing service for PSRT GHSA Bot."""

import base64
import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from githubkit import AppAuthStrategy, GitHub

from psrt_ghsa_bot.app import get_repository_advisories
from psrt_ghsa_bot.polyfills.comments import get_ghsa_comments
from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient
from psrt_ghsa_bot.state import StateManager

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class CommentProcessingStats:
    """Statistics for a comment processing run."""

    ghsas_checked: int = 0
    comments_found: int = 0
    errors: int = 0


def process_ghsa_comments(
    playwright_client: GitHubPlaywrightClient,
    owner: str,
    repo: str,
    ghsa_id: str,
) -> int:
    """Read comments for a single GHSA.

    Args:
        playwright_client: Playwright client for UI automation
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        Number of comments found
    """
    try:
        comments = get_ghsa_comments(playwright_client, owner, repo, ghsa_id)
    except PermissionError as e:
        logger.warning("Access denied to %s: %s", ghsa_id, e)
        return 0
    except Exception:
        logger.exception("Failed to fetch comments for %s", ghsa_id)
        return 0

    if not comments:
        logger.debug("No comments found on %s", ghsa_id)
        return 0

    logger.info("Found %d comments on %s", len(comments), ghsa_id)
    return len(comments)


def process_all_comments(
    github: GitHub,
    playwright_client: GitHubPlaywrightClient,
    state_manager: StateManager,
) -> CommentProcessingStats:
    """Process comments for all GHSAs across all installations.

    Args:
        github: Authenticated GitHub API client (app-level)
        playwright_client: Playwright client for UI automation
        state_manager: State manager for tracking processed commands

    Returns:
        CommentProcessingStats with run statistics
    """
    stats = CommentProcessingStats()
    installations = github.rest.paginate(github.rest.apps.list_installations)

    for installation_data in installations:
        installation_name = installation_data.account.login
        logger.info("Processing installation: %s", installation_name)

        installation_github = github.with_auth(github.auth.as_installation(installation_data.id))
        repos = installation_github.rest.paginate(
            installation_github.rest.apps.list_repos_accessible_to_installation,
            map_func=lambda r: r.parsed_data.repositories,
        )

        for repo in repos:
            owner = repo.owner.login
            repo_name = repo.name

            try:
                advisories = list(get_repository_advisories(installation_github, owner, repo_name))
                if not advisories:
                    continue

                count = len(advisories)
                logger.debug("Found %d advisories in %s/%s", count, owner, repo_name)

                for advisory in advisories:
                    ghsa_id = advisory["ghsa_id"]
                    state_str = advisory["state"]

                    if state_str not in ("triage", "draft"):
                        logger.debug("Skipping %s (state: %s)", ghsa_id, state_str)
                        continue

                    stats.ghsas_checked += 1
                    logger.info("Checking GHSA: %s/%s/%s (state: %s)", owner, repo_name, ghsa_id, state_str)
                    try:
                        comments_found = process_ghsa_comments(
                            playwright_client,
                            owner,
                            repo_name,
                            ghsa_id,
                        )
                        stats.comments_found += comments_found
                    except Exception:
                        logger.exception("Error processing %s", ghsa_id)
                        stats.errors += 1

            except Exception:
                logger.exception("Error accessing repository %s/%s", owner, repo_name)
                stats.errors += 1

    return stats


def main() -> None:
    """Cmment processing machine."""
    logger.info("PSRT GHSA Bot - Comment Processor")
    logger.info("=" * 50)

    logger.info("Initializing GitHub API client...")
    gh_client_private_key = base64.b64decode(os.environ["GH_CLIENT_PRIVATE_KEY"]).decode().strip()
    github = GitHub(AppAuthStrategy(os.environ["GH_CLIENT_ID"], gh_client_private_key))

    logger.info("Loading state manager...")
    state_manager = StateManager()
    state_manager.load()

    logger.info("Starting Playwright browser...")
    with GitHubPlaywrightClient() as playwright_client:
        logger.info("Authenticating to GitHub...")
        playwright_client.authenticate()
        logger.info("Authentication successful!")

        logger.info("Processing comments across all installations...")
        stats = process_all_comments(github, playwright_client, state_manager)

        logger.info("=" * 50)
        logger.info("Processing Summary:")
        logger.info("   GHSAs checked: %d", stats.ghsas_checked)
        logger.info("   Comments found: %d", stats.comments_found)
        logger.info("   Errors: %d", stats.errors)
        logger.info("=" * 50)

        logger.info("Saving state...")
        state_manager.save()
        logger.info("Done!")


if __name__ == "__main__":
    main()
