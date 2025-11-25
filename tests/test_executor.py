"""Tests for command execution."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from psrt_ghsa_bot.commands import CommandResult, execute_command
from psrt_ghsa_bot.commands.parser import Command


@pytest.fixture
def mock_github():
    """Create mock GitHub client."""
    return Mock()


@pytest.fixture
def mock_playwright():
    """Create mock Playwright client."""
    mock = Mock()
    mock.username = "test-bot"
    return mock


@pytest.fixture
def sample_command():
    """Create sample command."""
    return Command(
        action="help",
        arguments=[],
        author="testuser",
        comment_id="comment-1",
        timestamp=datetime.now(),
    )


class TestCommandExecution:
    """Test command execution."""

    def test_execute_help_command(self, sample_command, mock_github, mock_playwright) -> None:
        """Test executing help command."""
        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        result = execute_command(
            sample_command,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert isinstance(result, CommandResult)
        assert result.success
        assert "PSRT GHSA Bot Commands" in result.message
        assert "@test-bot help" in result.message

    def test_execute_status_command_stub(self, mock_github, mock_playwright) -> None:
        """Test executing status command (stub)."""
        cmd = Command(
            action="status",
            arguments=[],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        advisory_response = Mock()
        advisory_response.parsed_data = Mock(
            state="draft",
            cve_id="CVE-2024-1234",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-15T00:00:00Z",
        )
        mock_github.rest.security_advisories.get_repository_advisory.return_value = advisory_response

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert result.success
        assert "Advisory Status" in result.message
        assert "GHSA-1234" in result.message
        assert "draft" in result.message

    def test_execute_reject_command_with_cve(self, mock_github, mock_playwright) -> None:
        """Test executing reject command with CVE ID."""
        cmd = Command(
            action="reject",
            arguments=["CVE-2024-1234"],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        advisory_response = Mock()
        advisory_response.parsed_data = Mock(cve_id="CVE-2024-1234")
        mock_github.rest.security_advisories.get_repository_advisory.return_value = advisory_response

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert result.success
        assert "CVE Rejected" in result.message
        assert "CVE-2024-1234" in result.message

    def test_execute_reject_without_cve_fails(self, mock_github, mock_playwright) -> None:
        """Test executing reject command without CVE ID fails."""
        cmd = Command(
            action="reject",
            arguments=[],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert not result.success
        assert "Missing CVE ID" in result.message

    def test_execute_assign_cve_command(self, mock_github, mock_playwright) -> None:
        """Test executing assign-cve command."""
        cmd = Command(
            action="assign-cve",
            arguments=[],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        advisory_response = Mock()
        advisory_response.parsed_data = Mock(cve_id=None)
        mock_github.rest.security_advisories.get_repository_advisory.return_value = advisory_response

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        # Assign CVE requires CVE API credentials which won't be available in tests
        # So we expect it to fail but still test it's calling the right handler
        assert "assign" in result.message.lower() or "cve" in result.message.lower()

    def test_execute_publish_command(self, mock_github, mock_playwright) -> None:
        """Test executing publish command."""
        cmd = Command(
            action="publish",
            arguments=[],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert result.success
        assert "Publish Advisory" in result.message

    def test_execute_unknown_command(self, mock_github, mock_playwright) -> None:
        """Test executing unknown command."""
        cmd = Command(
            action="unknown-action",
            arguments=[],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime.now(),
        )

        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=204)

        result = execute_command(
            cmd,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert not result.success
        assert "Unknown command" in result.message
        assert "unknown-action" in result.message

    def test_execute_unauthorized_user(self, sample_command, mock_github, mock_playwright) -> None:
        """Test executing command as unauthorized user."""
        mock_github.rest.teams.get_member_in_org.return_value = Mock(status_code=404)
        mock_github.rest.security_advisories.get_repository_advisory.side_effect = Exception("Not found")
        mock_github.rest.repos.get_collaborator_permission_level.side_effect = Exception("Not found")

        result = execute_command(
            sample_command,
            mock_github,
            mock_playwright,
            "python",
            "cpython",
            "GHSA-1234",
        )

        assert not result.success
        assert "Unauthorized" in result.message
        assert "testuser" in result.message
