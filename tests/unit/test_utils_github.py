"""Tests for psrt_ghsa_bot.utils.github module."""

import base64
from unittest import mock

from githubkit import GitHub
from githubkit.exception import RequestFailed

from psrt_ghsa_bot.utils.github import (
    get_github_client,
    get_workflow_runs,
    iter_installation_repos,
)


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


def test_get_workflow_runs_returns_list():
    """Test that get_workflow_runs returns a list of run dicts."""
    mock_github = mock.MagicMock()
    mock_run = mock.MagicMock()
    mock_run.status = "completed"
    mock_run.conclusion = "success"
    mock_run.id = 12345

    mock_github.rest.actions.list_workflow_runs.return_value.parsed_data.workflow_runs = [mock_run]

    runs = get_workflow_runs(mock_github, "owner", "repo", "workflow.yml")

    assert runs == [{"status": "completed", "conclusion": "success", "id": 12345}]
    mock_github.rest.actions.list_workflow_runs.assert_called_once_with(
        owner="owner",
        repo="repo",
        workflow_id="workflow.yml",
        per_page=5,
    )


def test_get_workflow_runs_handles_request_failed():
    """Test that get_workflow_runs returns empty list on RequestFailed."""
    mock_github = mock.MagicMock()
    mock_github.rest.actions.list_workflow_runs.side_effect = RequestFailed(mock.MagicMock())

    runs = get_workflow_runs(mock_github, "owner", "repo", "workflow.yml")

    assert runs == []


def test_iter_installation_repos_yields_tuples():
    """Test that iter_installation_repos yields (github, repo) tuples."""
    mock_github = mock.MagicMock()

    mock_installation = mock.MagicMock()
    mock_installation.id = 123

    mock_repo = mock.MagicMock()
    mock_repo.owner.login = "test-owner"
    mock_repo.name = "test-repo"

    mock_github.rest.paginate.side_effect = [
        [mock_installation],
        [mock_repo],
    ]

    mock_installation_github = mock.MagicMock()
    mock_github.with_auth.return_value = mock_installation_github
    mock_installation_github.rest.paginate.return_value = [mock_repo]

    results = list(iter_installation_repos(mock_github))

    assert len(results) == 1
    assert results[0][0] == mock_installation_github
    assert results[0][1] == mock_repo
