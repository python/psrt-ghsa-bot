"""Tests for command parsing system.

todo: test for auth checks to make sure they are handled properly
"""

import os
from datetime import UTC, datetime

import pytest

from psrt_ghsa_bot.commands.parser import (
    AVAILABLE_COMMANDS,
    Command,
    get_help_text,
    get_unknown_command_response,
    is_valid_command,
    parse_command,
)


@pytest.fixture
def bot_username() -> str:
    """Get bot username from environment or use default."""
    return os.environ.get("GH_BOT_USERNAME", "psrt-ghsabot")


class TestCommandParsing:
    """Test command parsing from comment text."""

    def test_parse_simple_command(self) -> None:
        """Test parsing a simple command without arguments."""
        result = parse_command(
            "@psrt-ghsabot help",
            "testuser",
            "comment-1",
            "psrt-ghsabot",
            datetime(2024, 1, 1, 12, 0, 0),
        )

        assert result is not None
        assert result.action == "help"
        assert result.arguments == []
        assert result.author == "testuser"
        assert result.comment_id == "comment-1"
        assert result.timestamp == datetime(2024, 1, 1, 12, 0, 0)

    def test_parse_command_with_single_argument(self) -> None:
        """Test parsing command with one argument."""
        result = parse_command(
            "@psrt-ghsabot reject CVE-2024-1234",
            "maintainer",
            "comment-2",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.action == "reject"
        assert result.arguments == ["CVE-2024-1234"]
        assert result.author == "maintainer"

    def test_parse_command_with_multiple_arguments(self) -> None:
        """Test parsing command with multiple arguments."""
        result = parse_command(
            "@psrt-ghsabot some-cmd arg1 arg2 arg3",
            "user",
            "comment-3",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.action == "some-cmd"
        assert result.arguments == ["arg1", "arg2", "arg3"]

    def test_parse_command_case_insensitive(self) -> None:
        """Test that bot mention and command are case-insensitive."""
        variations = [
            "@PSRT-GHSABOT help",
            "@Psrt-GhsaBot help",
            "@psrt-ghsabot HELP",
            "@psrt-ghsabot Help",
        ]

        for text in variations:
            result = parse_command(text, "user", "comment", "psrt-ghsabot")
            assert result is not None
            assert result.action == "help"

    def test_parse_command_in_middle_of_text(self) -> None:
        """Test parsing command embedded in larger comment."""
        comment = """
        I think we should handle this differently.

        @psrt-ghsabot reject CVE-2024-5678

        Let me know if you agree.
        """

        result = parse_command(comment, "user", "comment", "psrt-ghsabot")
        assert result is not None
        assert result.action == "reject"
        assert result.arguments == ["CVE-2024-5678"]

    def test_parse_command_with_extra_whitespace(self) -> None:
        """Test parsing handles extra whitespace correctly."""
        result = parse_command(
            "@psrt-ghsabot    reject    CVE-2024-9999",
            "user",
            "comment",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.action == "reject"
        assert result.arguments == ["CVE-2024-9999"]

    def test_parse_command_with_alias(self) -> None:
        """Test that command aliases work correctly."""
        result = parse_command(
            "@psrt-ghsabot withdraw CVE-2024-1111",
            "user",
            "comment",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.action == "reject"
        assert result.arguments == ["CVE-2024-1111"]

    def test_parse_publish_command(self) -> None:
        """Test parsing publish command."""
        result = parse_command(
            "@psrt-ghsabot publish",
            "user",
            "comment",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.action == "publish"
        assert result.arguments == []

    def test_parse_publish_aliases(self) -> None:
        """Test that publish aliases work correctly."""
        for alias in ["release", "complete"]:
            result = parse_command(
                f"@psrt-ghsabot {alias}",
                "user",
                "comment",
                "psrt-ghsabot",
            )

            assert result is not None
            assert result.action == "publish"

    def test_parse_no_command(self) -> None:
        """Test that None is returned when no command is found."""
        result = parse_command(
            "Just a regular comment without bot mention",
            "user",
            "comment",
            "psrt-ghsabot",
        )

        assert result is None

    def test_parse_incomplete_mention(self) -> None:
        """Test that incomplete mentions don't parse."""
        result = parse_command("@psrt", "user", "comment", "psrt-ghsabot")
        assert result is None

        result = parse_command("psrt-ghsabot help", "user", "comment", "psrt-ghsabot")
        assert result is None

    def test_parse_empty_comment(self) -> None:
        """Test parsing empty or None comment."""
        assert parse_command("", "user", "comment", "psrt-ghsabot") is None
        assert parse_command(None, "user", "comment", "psrt-ghsabot") is None

    def test_parse_command_default_timestamp(self) -> None:
        """Test that timestamp defaults to current time."""
        before = datetime.now(tz=UTC)
        result = parse_command("@psrt-ghsabot help", "user", "comment", "psrt-ghsabot")
        after = datetime.now(tz=UTC)

        assert result is not None
        assert before <= result.timestamp <= after

    def test_parse_command_custom_bot_username(self) -> None:
        """Test parsing with custom bot username."""
        result = parse_command(
            "@my-custom-bot reject CVE-2024-9999",
            "user",
            "comment",
            "my-custom-bot",
        )

        assert result is not None
        assert result.action == "reject"
        assert result.arguments == ["CVE-2024-9999"]

    def test_parse_command_username_with_special_chars(self) -> None:
        """Test parsing bot username with regex special characters."""
        result = parse_command(
            "@bot.test+dev reject CVE-2024-9999",
            "user",
            "comment",
            "bot.test+dev",
        )

        assert result is not None
        assert result.action == "reject"


class TestCommandValidation:
    """Test command validation functions."""

    def test_is_valid_command_recognized(self) -> None:
        """Test that recognized commands are valid."""
        for cmd in AVAILABLE_COMMANDS:
            assert is_valid_command(cmd)

    def test_is_valid_command_case_insensitive(self) -> None:
        """Test validation is case-insensitive."""
        assert is_valid_command("HELP")
        assert is_valid_command("Help")
        assert is_valid_command("reject")
        assert is_valid_command("REJECT")

    def test_is_valid_command_unrecognized(self) -> None:
        """Test that unrecognized commands are invalid."""
        assert not is_valid_command("unknown")
        assert not is_valid_command("foo")
        assert not is_valid_command("delete-everything")

    def test_is_valid_command_publish(self) -> None:
        """Test that publish command is recognized."""
        assert is_valid_command("publish")
        assert is_valid_command("PUBLISH")
        assert is_valid_command("Publish")


class TestHelpText:
    """Test help text generation."""

    def test_get_help_text_format(self) -> None:
        """Test that help text is properly formatted."""
        help_text = get_help_text("psrt-ghsabot")

        assert "PSRT GHSA Bot Commands" in help_text
        assert "Available commands:" in help_text

        for cmd_name, cmd_info in AVAILABLE_COMMANDS.items():
            assert cmd_name in help_text.lower()
            assert cmd_info["description"] in help_text
            assert f"@psrt-ghsabot {cmd_info['usage']}" in help_text
            assert f"@psrt-ghsabot {cmd_info['example']}" in help_text

    def test_get_help_text_includes_all_commands(self) -> None:
        """Test that all commands are documented in help."""
        help_text = get_help_text("psrt-ghsabot")

        for cmd_name in AVAILABLE_COMMANDS:
            assert cmd_name in help_text.lower()

    def test_get_help_text_shows_aliases(self) -> None:
        """Test that command aliases are shown in help."""
        help_text = get_help_text("psrt-ghsabot")

        assert "withdraw" in help_text
        assert "request-cve" in help_text
        assert "release" in help_text
        assert "complete" in help_text

    def test_get_help_text_custom_bot_username(self) -> None:
        """Test help text with custom bot username."""
        help_text = get_help_text("my-custom-bot")

        assert "@my-custom-bot help" in help_text
        assert "@my-custom-bot reject" in help_text
        assert "@my-custom-bot publish" in help_text
        assert "@psrt-ghsabot" not in help_text


class TestUnknownCommandResponse:
    """Test unknown command response generation."""

    def test_get_unknown_command_response_includes_action(self) -> None:
        """Test that response includes the unknown action."""
        response = get_unknown_command_response("foo")

        assert "foo" in response
        assert "Unknown command" in response

    def test_get_unknown_command_response_lists_available(self) -> None:
        """Test that response lists available commands."""
        response = get_unknown_command_response("invalid")

        for cmd in AVAILABLE_COMMANDS:
            assert cmd in response.lower()

    def test_get_unknown_command_response_suggests_help(self, bot_username: str) -> None:
        """Test that response suggests using help."""
        response = get_unknown_command_response("bad", bot_username)

        assert "help" in response.lower()
        assert f"@{bot_username} help" in response


class TestCommandRepresentation:
    """Test Command dataclass methods."""

    def test_command_repr(self) -> None:
        """Test Command __repr__ output."""
        cmd = Command(
            action="reject",
            arguments=["CVE-2024-1234"],
            author="testuser",
            comment_id="comment-1",
            timestamp=datetime(2024, 1, 1),
        )

        repr_str = repr(cmd)
        assert "reject" in repr_str
        assert "CVE-2024-1234" in repr_str
        assert "testuser" in repr_str

    def test_command_repr_no_arguments(self) -> None:
        """Test Command __repr__ with no arguments."""
        cmd = Command(
            action="help",
            arguments=[],
            author="user",
            comment_id="comment",
            timestamp=datetime.now(),
        )

        repr_str = repr(cmd)
        assert "help" in repr_str
        assert "(no args)" in repr_str


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_command_with_special_characters_in_args(self) -> None:
        """Test parsing arguments with special characters."""
        result = parse_command(
            "@psrt-ghsabot test arg-with-dash arg_with_underscore",
            "user",
            "comment",
            "psrt-ghsabot",
        )

        assert result is not None
        assert result.arguments == ["arg-with-dash", "arg_with_underscore"]

    def test_multiple_bot_mentions(self) -> None:
        """Test that only first mention is parsed."""
        comment = """
        @psrt-ghsabot help

        Actually, wait:
        @psrt-ghsabot status
        """

        result = parse_command(comment, "user", "comment", "psrt-ghsabot")
        assert result is not None
        assert result.action == "help"

    def test_command_at_start_of_line(self) -> None:
        """Test command at beginning of comment."""
        result = parse_command(
            "@psrt-ghsabot reject CVE-2024-1234",
            "user",
            "comment",
            "psrt-ghsabot",
        )
        assert result is not None

    def test_command_at_end_of_line(self) -> None:
        """Test command at end of comment."""
        result = parse_command(
            "Here's my command: @psrt-ghsabot help",
            "user",
            "comment",
            "psrt-ghsabot",
        )
        assert result is not None

    def test_command_on_its_own_line(self) -> None:
        """Test command on a line by itself."""
        comment = """
        Some context here.

        @psrt-ghsabot reject CVE-2024-1234

        More context below.
        """
        result = parse_command(comment, "user", "comment", "psrt-ghsabot")
        assert result is not None
        assert result.action == "reject"
