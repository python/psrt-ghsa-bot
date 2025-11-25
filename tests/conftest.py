"""Shared pytest config & fixtures."""

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from psrt_ghsa_bot.polyfills import GitHubPlaywrightClient

if TYPE_CHECKING:
    from collections.abc import Generator

PLAYWRIGHT_FULL = Path("tests/PLAYWRIGHT_FULL.test").exists()
AUTH_STATE_EXISTS = Path("playwright/.auth/github_state.json").exists()

requires_playwright_auth = pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and AUTH_STATE_EXISTS),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)


@pytest.fixture
def client() -> GitHubPlaywrightClient:
    """Create a GitHubPlaywrightClient instance for testing."""
    return GitHubPlaywrightClient(headless=True)


@pytest.fixture
def authenticated_client() -> Generator[GitHubPlaywrightClient]:
    """Create an authenticated GitHubPlaywrightClient instance for testing."""
    client = GitHubPlaywrightClient(headless=True)
    client.start()
    client.authenticate()
    yield client
    client.close()


@pytest.fixture
def test_ghsa() -> Generator[dict[str, str]]:
    """Create a test GHSA and clean it up after the test.

    Returns dict with: owner, repo, ghsa_id
    """
    from githubkit import GitHub, TokenAuthStrategy  # noqa: PLC0415

    token = os.getenv("GH_AUTH_TOKEN")
    if not token:
        pytest.skip("GH_AUTH_TOKEN not set")

    github = GitHub(TokenAuthStrategy(token))  # type: ignore[arg-type]
    owner = "jolt-org"
    repo = "ghsa-testing"

    response = github.rest.security_advisories.create_repository_advisory(
        owner=owner,
        repo=repo,
        data={
            "summary": f"Test Advisory {datetime.now().timestamp()}",
            "description": "This is a test advisory created by pytest. It will be deleted automatically.",
            "severity": "low",
            "vulnerabilities": [
                {
                    "package": {"ecosystem": "pip", "name": "test-package"},
                    "vulnerable_version_range": "< 1.0.0",
                }
            ],
        },
    )

    ghsa_id = response.parsed_data.ghsa_id

    yield {"owner": owner, "repo": repo, "ghsa_id": ghsa_id}

    try:
        github.rest.security_advisories.update_repository_advisory(
            owner=owner,
            repo=repo,
            ghsa_id=ghsa_id,
            data={"state": "closed"},
        )
    except Exception:
        pass
