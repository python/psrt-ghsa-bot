"""Tests for the Playwright base client."""

from pathlib import Path

import pytest

from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient


@pytest.fixture
def client() -> GitHubPlaywrightClient:
    """Create a GitHubPlaywrightClient instance for testing."""
    return GitHubPlaywrightClient(headless=True)


def test_client_context_manager():
    """Test that the client works as a context manager."""
    with GitHubPlaywrightClient(headless=True) as client:
        assert client.page is not None
        assert client.context is not None


def test_client_start_and_close(client: GitHubPlaywrightClient):
    """Test that the client can be started and closed manually."""
    client.start()
    assert client.page is not None
    assert client.context is not None

    client.close()
    with pytest.raises(RuntimeError):
        _ = client.page


def test_navigate_to_public_page(client: GitHubPlaywrightClient):
    """Test navigation to a public GitHub page."""
    with client:
        client.page.goto("https://github.com")
        assert "github.com" in client.page.url


@pytest.mark.skipif(
    not Path("playwright/.auth/github_state.json").exists(),
    reason="Requires existing auth state (PAT tokens don't work for web UI auth)",
)
def test_authentication_with_saved_state(client: GitHubPlaywrightClient):
    """Test authentication using saved state from manual login."""
    with client:
        client.authenticate()
        assert client._is_authenticated()


@pytest.mark.skipif(
    not Path("playwright/.auth/github_state.json").exists(),
    reason="Requires existing authentication state",
)
def test_navigate_to_ghsa_page(client: GitHubPlaywrightClient):
    """Test navigation to a GHSA page (requires authentication)."""
    with client:
        client.authenticate()

        # ! TODO: will need to use different org/repo later?
        client.navigate_to_ghsa("jolt-org", "ghsa-testing", "GHSA-f3x5-4pp6-r2mf")

        assert "GHSA-f3x5-4pp6-r2mf" in client.page.url
        assert "security/advisories" in client.page.url


@pytest.mark.skipif(
    not Path("playwright/.auth/github_state.json").exists(),
    reason="Requires existing authentication state",
)
def test_authentication_state_persistence(client: GitHubPlaywrightClient):
    """Test that authentication state is saved and can be reused."""
    storage_state_path = Path("playwright/.auth/github_state.json")

    with client:
        if storage_state_path.exists():
            assert client._is_authenticated()

    assert storage_state_path.exists()


def test_wait_for_page_ready(client: GitHubPlaywrightClient):
    """Test the wait_for_page_ready helper."""
    with client:
        client.page.goto("https://github.com")
        client.wait_for_page_ready(timeout=10000)


@pytest.mark.skip(
    reason="Manual test - run explicitly with: pytest tests/test_playwright_base.py::test_manual_authentication -v"
)
def test_manual_authentication():
    """Test manual authentication flow.

        This test is marked as manual and should be run explicitly when needed
        to set up initial authentication.
    /
        Only really for localdev bcecause we want CI to be automagic ✨ so use PAT for that

        Run with: pytest tests/test_playwright_base.py::test_manual_authentication -v
    """
    with GitHubPlaywrightClient(headless=False) as client:
        client.authenticate_manual(timeout=120000)  # 2 minutes
        assert client._is_authenticated()
