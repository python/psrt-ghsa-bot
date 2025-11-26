"""Tests for psrt_ghsa_bot.utils.github module."""

import base64
from unittest import mock

from githubkit import GitHub

from psrt_ghsa_bot.utils.github import get_github_client


def test_get_github_client_returns_github_instance():
    """Test that get_github_client returns a GitHub client."""
    fake_private_key = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
    encoded_key = base64.b64encode(fake_private_key.encode()).decode()

    with mock.patch("psrt_ghsa_bot.utils.github.settings") as mock_settings:
        mock_settings.github.GH_CLIENT_ID = "test-client-id"
        mock_settings.github.GH_CLIENT_PRIVATE_KEY = encoded_key

        client = get_github_client()

        assert isinstance(client, GitHub)


def test_get_github_client_decodes_base64_key():
    """Test that get_github_client properly decodes base64-encoded private key."""
    fake_private_key = "-----BEGIN RSA PRIVATE KEY-----\ntest-key-content\n-----END RSA PRIVATE KEY-----"
    encoded_key = base64.b64encode(fake_private_key.encode()).decode()

    with (
        mock.patch("psrt_ghsa_bot.utils.github.settings") as mock_settings,
        mock.patch("psrt_ghsa_bot.utils.github.GitHub") as mock_github,
        mock.patch("psrt_ghsa_bot.utils.github.AppAuthStrategy") as mock_auth_strategy,
    ):
        mock_settings.github.GH_CLIENT_ID = "test-client-id"
        mock_settings.github.GH_CLIENT_PRIVATE_KEY = encoded_key

        get_github_client()

        mock_auth_strategy.assert_called_once_with("test-client-id", fake_private_key)
        mock_github.assert_called_once()
