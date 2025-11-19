"""Command parser for extracting bot commands from GHSA comments."""

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict


class CommandInfo(TypedDict, total=False):
    """Type definition for command metadata because type checke rhates me."""

    description: str
    usage: str
    example: str
    aliases: list[str]


@dataclass
class Command:
    """Represents a parsed command from a GHSA comment."""

    action: str
    """The command action (e.g., 'help', 'reject', 'assign-cve')"""
    arguments: list[str]
    """List of arguments provided to the command"""
    author: str
    """GitHub username who issued the command"""
    comment_id: str
    """ID of the comment containing the command"""
    timestamp: datetime
    """When the command was issued"""

    def __repr__(self) -> str:
        args_str = " ".join(self.arguments) if self.arguments else "(no args)"
        return f"Command({self.action} {args_str} by {self.author})"


AVAILABLE_COMMANDS: dict[str, CommandInfo] = {
    "help": {
        "description": "Show this help message with all available commands",
        "usage": "help",
        "example": "help",
    },
    "reject": {
        "description": "Reject/withdraw a CVE ID for this advisory",
        "usage": "reject <CVE-ID>",
        "example": "reject CVE-2024-1234",
        "aliases": ["withdraw"],
    },
    "assign-cve": {
        "description": "Request CVE ID assignment for this advisory",
        "usage": "assign-cve",
        "example": "assign-cve",
        "aliases": ["request-cve"],
    },
    "status": {
        "description": "Show current status of this advisory and associated CVE",
        "usage": "status",
        "example": "status",
    },
    "publish": {
        "description": "Publish this advisory and associated CVE ID",
        "usage": "publish",
        "example": "publish",
        "aliases": ["release", "complete"],
    },
}

COMMAND_ALIASES = {
    "withdraw": "reject",
    "request-cve": "assign-cve",
    "release": "publish",
    "complete": "publish",
}


def _build_command_pattern(bot_username: str) -> re.Pattern[str]:
    """Build regex pattern for matching bot commands.

    Args:
        bot_username: The bot's GitHub username.. gotten from env var.

    Returns:
        Compiled regex pattern that matches @<bot-username> <command> [args]
    """
    escaped_username = re.escape(bot_username)
    return re.compile(
        rf"@{escaped_username}\s+(\S+)(?:\s+(.+))?",
        re.IGNORECASE | re.MULTILINE,
    )


def parse_command(
    comment_body: str | None,
    author: str,
    comment_id: str,
    bot_username: str,
    timestamp: datetime | None = None,
) -> Command | None:
    """Parse a command from a comment body.

    Looks for pattern: @<bot-username> <action> [arguments...]

    Args:
        comment_body: The full text of the comment
        author: GitHub username who wrote the comment
        comment_id: Unique identifier for the comment
        bot_username: GitHub username of the bot to look for
        timestamp: When the comment was created (defaults to now)

    Returns:
        Parsed Command object, or None if no valid command found

    Example:
        >>> parse_command(
        ...     "@<bot-username> reject CVE-2024-1234",
        ...     "JacobCoffee",
        ...     "comment-123",
        ...     "<bot-username>"
        ... )
        Command(reject CVE-2024-1234 by JacobCoffee)
    """
    if not comment_body:
        return None

    pattern = _build_command_pattern(bot_username)
    match = pattern.search(comment_body)
    if not match:
        return None

    action = match.group(1).lower()
    action = COMMAND_ALIASES.get(action, action)

    arguments_str = match.group(2)
    arguments = arguments_str.split() if arguments_str else []

    if timestamp is None:
        timestamp = datetime.now()

    return Command(
        action=action,
        arguments=arguments,
        author=author,
        comment_id=comment_id,
        timestamp=timestamp,
    )


def is_valid_command(action: str) -> bool:
    """Check if an action is a recognized command.

    Args:
        action: The command action to validate

    Returns:
        True if the action is recognized, False otherwise
    """
    return action.lower() in AVAILABLE_COMMANDS


def get_help_text(bot_username: str | None = None) -> str:
    """Generate help text listing all available commands.

    Args:
        bot_username: The bot's GitHub username to use in examples.
                     Defaults to GH_BOT_USERNAME environment variable.

    Returns:
        Formatted markdown help text
    """
    lines = [
        "# PSRT GHSA Bot Commands",
        "",
        "Available commands:",
        "",
    ]

    for cmd_info in AVAILABLE_COMMANDS.values():
        usage = f"@{bot_username} {cmd_info['usage']}"
        example = f"@{bot_username} {cmd_info['example']}"

        lines.append(f"### `{usage}`")
        lines.append(cmd_info["description"])
        lines.append(f"**Example:** `{example}`")

        if "aliases" in cmd_info:
            aliases = ", ".join(f"`{alias}`" for alias in cmd_info["aliases"])
            lines.append(f"**Aliases:** {aliases}")

        lines.append("")

    lines.extend(
        [
            "--",
            "",
            f"_To use a command, mention `@{bot_username}` followed by the command name and any required arguments._",
            "",
            "_Only members of the `python/psrt` team and advisory collaborators can execute commands._",
        ]
    )

    return "\n".join(lines)


def get_unknown_command_response(action: str, bot_username: str | None = None) -> str:
    """Generate response message for unknown commands.

    Args:
        action: The unrecognized command action
        bot_username: The bot's GitHub username to use in help message.
                     Defaults to GH_BOT_USERNAME environment variable.

    Returns:
        Formatted error message with help text
    """
    if bot_username is None:
        bot_username = os.environ.get("GH_BOT_USERNAME", "psrt-ghsabot")

    available = ", ".join(f"`{cmd}`" for cmd in AVAILABLE_COMMANDS)

    return (
        f"❌ Unknown command: `{action}`\n\n"
        f"Available commands: {available}\n\n"
        f"Use `@{bot_username} help` for detailed usage information."
    )
