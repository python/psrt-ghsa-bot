"""Unit tests for the Playwright base client."""

import pytest

from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient


@pytest.fixture
def client() -> GitHubPlaywrightClient:
    """Create a GitHubPlaywrightClient instance for testing."""
    return GitHubPlaywrightClient(headless=True)


def test_client_context_manager() -> None:
    """Test that the client works as a context manager."""
    with GitHubPlaywrightClient(headless=True) as client:
        assert client.page is not None
        assert client.context is not None


def test_client_start_and_close(client: GitHubPlaywrightClient) -> None:
    """Test that the client can be started and closed manually."""
    client.start()
    assert client.page is not None
    assert client.context is not None

    client.close()
    with pytest.raises(RuntimeError):
        _ = client.page
