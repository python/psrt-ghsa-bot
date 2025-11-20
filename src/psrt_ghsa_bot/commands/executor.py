"""Command execution engine for PSRT GHSA Bot.

TODO: Maybe we should look into easily extensiblke commands
 like how discord.py or others do it so it can autodiscover
 cmds and register them and keep this file just for the
 executor, auth, results, and parser...
"""

import os
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from cvelib.cve_api import CveApi

from psrt_ghsa_bot.api_app import reserve_one_cve
from psrt_ghsa_bot.commands.authorization import AuthorizationResult, is_authorized
from psrt_ghsa_bot.commands.parser import Command, get_help_text, get_unknown_command_response
from psrt_ghsa_bot.state import StateManager

if TYPE_CHECKING:
    from githubkit import GitHub

    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient


@dataclass
class CommandResult:
    """Result of command execution."""

    success: bool
    """Whether the command executed successfully"""
    message: str
    """Response message to post as comment"""
    error: Exception | None = None
    """Exception if command failed"""


def execute_command(
    cmd: Command,
    github: GitHub,
    playwright_client: GitHubPlaywrightClient,
    owner: str,
    repo: str,
    ghsa_id: str,
) -> CommandResult:
    """Execute a parsed command.

    Example: "@<bot-username> assign-cve"

    These are based on src/psrt_ghsa_bot/commands/parser.py:AVAILABLE_COMMANDS
    and do an auth check before trying.

    Args:
        cmd: Parsed command to execute
        github: Authenticated GitHub API client
        playwright_client: Playwright client for UI automation
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with success status and response message
    """
    # TODO: i dont like this.. it will just grow and grow...
    auth_result = is_authorized(github, cmd.author, owner, repo, ghsa_id)

    if not auth_result.authorized:
        return _unauthorized_result(cmd, auth_result)

    if cmd.action == "help":
        return _handle_help(playwright_client)

    if cmd.action == "status":
        return _handle_status(cmd, github, owner, repo, ghsa_id)

    if cmd.action == "reject":
        return _handle_reject(cmd, github, owner, repo, ghsa_id)

    if cmd.action == "assign-cve":
        return _handle_assign_cve(cmd, github, owner, repo, ghsa_id)

    if cmd.action == "publish":
        return _handle_publish(cmd, github, owner, repo, ghsa_id)

    if cmd.action == "set-deadline":
        return _handle_set_deadline(cmd, owner, repo, ghsa_id)

    if cmd.action == "set-warning-days":
        return _handle_set_warning_days(cmd, owner, repo, ghsa_id)

    if cmd.action == "set-team":
        return _handle_set_team(cmd, owner, repo, ghsa_id)

    return CommandResult(
        success=False,
        message=get_unknown_command_response(cmd.action, playwright_client.username),
    )


def _unauthorized_result(cmd: Command, auth_result: AuthorizationResult) -> CommandResult:
    """Generate result for unauthorized command attempt.

    Args:
        cmd: The command that was attempted
        auth_result: Authorization check result

    Returns:
        CommandResult with unauthorized message
    """
    message = (
        f"❌ **Unauthorized**\n\n"
        f"@{cmd.author}, you are not authorized to execute bot commands.\n\n"
        f"**Reason:** {auth_result.reason}\n\n"
        f"Only members of the `python/psrt` team and advisory collaborators can use bot commands."
    )

    return CommandResult(success=False, message=message)


def _handle_help(playwright_client: GitHubPlaywrightClient) -> CommandResult:
    """Handle help command.

    Args:
        playwright_client: Playwright client (for bot username)

    Returns:
        CommandResult with help text
    """
    help_text = get_help_text(playwright_client.username)
    return CommandResult(success=True, message=help_text)


def _handle_status(_cmd: Command, github: GitHub, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle status command.

    Args:
        cmd: Parsed command
        github: GitHub API client
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with status information
    """
    try:
        advisory = github.rest.security_advisories.get_repository_advisory(owner=owner, repo=repo, ghsa_id=ghsa_id)

        state = advisory.parsed_data.state
        cve_id = advisory.parsed_data.cve_id or "None assigned"
        created_at = advisory.parsed_data.created_at
        updated_at = advisory.parsed_data.updated_at
        created = datetime.fromisoformat(created_at)
        days_old = (datetime.now(created.tzinfo) - created).days

        message = (
            f"📊 **Advisory Status**\n\n"
            f"**Repository:** {owner}/{repo}\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**State:** {state}\n"
            f"**CVE ID:** {cve_id}\n"
            f"**Created:** {days_old} days ago\n"
            f"**Last Updated:** {updated_at}"
        )

        return CommandResult(success=True, message=message)

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to get advisory status: {e!s}",
            error=e,
        )


def _handle_reject(cmd: Command, github: GitHub, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle CVE rejection command.

    Args:
        cmd: Parsed command
        github: GitHub API client
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with rejection confirmation
    """
    if not cmd.arguments:
        return CommandResult(
            success=False,
            message="❌ **Error:** Missing CVE ID\n\nUsage: `reject <CVE-ID>`\n\nExample: `reject CVE-2024-1234`",
        )

    cve_id = cmd.arguments[0]

    try:
        advisory = github.rest.security_advisories.get_repository_advisory(owner=owner, repo=repo, ghsa_id=ghsa_id)

        current_cve = advisory.parsed_data.cve_id

        if current_cve is None:
            return CommandResult(
                success=False,
                message=f"❌ **Error:** Advisory {ghsa_id} has no CVE ID assigned.",
            )

        if current_cve != cve_id:
            return CommandResult(
                success=False,
                message=(
                    f"❌ **Error:** CVE ID mismatch\n\n"
                    f"Advisory {ghsa_id} is associated with {current_cve}, not {cve_id}."
                ),
            )

        github.rest.security_advisories.update_repository_advisory(
            owner=owner,
            repo=repo,
            ghsa_id=ghsa_id,
            data={"cve_id": None},
        )

        message = (
            f"🚫 **CVE Rejected**\n\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**CVE ID:** {cve_id}\n\n"
            f"The CVE ID has been removed from this advisory.\n\n"
            f"_Note: This does not withdraw the CVE from the CVE system. "
            f"CVE rejection via API requires additional CVE API integration._"
        )

        return CommandResult(success=True, message=message)

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to reject CVE: {e!s}",
            error=e,
        )


def _handle_assign_cve(cmd: Command, github: GitHub, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle CVE assignment command.

    Args:
        cmd: Parsed command
        github: GitHub API client
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with assignment confirmation
    """
    try:
        advisory = github.rest.security_advisories.get_repository_advisory(owner=owner, repo=repo, ghsa_id=ghsa_id)
        current_cve = advisory.parsed_data.cve_id

        if current_cve is not None:
            return CommandResult(
                success=False,
                message=(
                    f"**CVE Already Assigned**\n\n"
                    f"Advisory {ghsa_id} already has CVE ID {current_cve} assigned.\n\n"
                    f"Use `status` to view advisory details or `reject {current_cve}` to remove it."
                ),
            )

        cve_api = CveApi(
            org="PSF",
            username=os.environ["CVE_USERNAME"],
            api_key=os.environ["CVE_API_KEY"],
            env=os.environ.get("CVE_ENV", "prod"),
        )

        cve_id = reserve_one_cve(cve_api)

        github.rest.security_advisories.update_repository_advisory(
            owner=owner,
            repo=repo,
            ghsa_id=ghsa_id,
            data={"cve_id": cve_id},
        )

        message = (
            f"🔖 **CVE Assigned**\n\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**CVE ID:** {cve_id}\n\n"
            f"A new CVE ID has been reserved and associated with this advisory."
        )

        return CommandResult(success=True, message=message)

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to assign CVE: {e!s}",
            error=e,
        )


def _handle_publish(cmd: Command, github: GitHub, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle advisory publication command.

    Args:
        cmd: Parsed command
        github: GitHub API client
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with publication confirmation
    """
    message = "📢 **Publish Advisory** (Stub)\n\nbut for now I am just a stub cmd :)"

    return CommandResult(success=True, message=message)


def _handle_set_deadline(cmd: Command, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle set-deadline command.

    Args:
        cmd: Parsed command
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with deadline confirmation
    """
    if not cmd.arguments:
        return CommandResult(
            success=False,
            message="❌ **Error:** Missing deadline days\n\nUsage: `set-deadline <days>`\n\nExample: `set-deadline 60`",
        )

    try:
        days = int(cmd.arguments[0])
        if days <= 0:
            return CommandResult(
                success=False,
                message=f"❌ **Error:** Deadline must be a positive number of days (got {days})",
            )

        state_manager = StateManager()
        ghsa_state = state_manager.get_ghsa_state(f"{owner}/{repo}/{ghsa_id}")
        ghsa_state.deadline_days = days
        state_manager.save()

        message = (
            f"⏰ **Deadline Set**\n\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**Deadline:** {days} days from advisory creation\n\n"
            f"Inactivity reminders will be sent when approaching this deadline."
        )

        return CommandResult(success=True, message=message)

    except ValueError:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Invalid number: '{cmd.arguments[0]}'\n\nDeadline must be a positive integer.",
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to set deadline: {e!s}",
            error=e,
        )


def _handle_set_warning_days(cmd: Command, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle set-warning-days command.

    Args:
        cmd: Parsed command
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with warning threshold confirmation
    """
    if not cmd.arguments:
        return CommandResult(
            success=False,
            message=(
                "❌ **Error:** Missing warning threshold days\n\n"
                "Usage: `set-warning-days <days>`\n\n"
                "Example: `set-warning-days 14`"
            ),
        )

    try:
        days = int(cmd.arguments[0])
        if days <= 0:
            return CommandResult(
                success=False,
                message=f"❌ **Error:** Warning threshold must be a positive number of days (got {days})",
            )

        state_manager = StateManager()
        ghsa_state = state_manager.get_ghsa_state(f"{owner}/{repo}/{ghsa_id}")
        ghsa_state.warning_threshold_days = days
        state_manager.save()

        message = (
            f"⚠️ **Warning Threshold Set**\n\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**Warning Threshold:** {days} days before deadline\n\n"
            f"Inactivity reminders will start {days} days before the deadline if there has been no activity."
        )

        return CommandResult(success=True, message=message)

    except ValueError:
        return CommandResult(
            success=False,
            message=(
                f"❌ **Error:** Invalid number: '{cmd.arguments[0]}'\n\nWarning threshold must be a positive integer."
            ),
        )
    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to set warning threshold: {e!s}",
            error=e,
        )


def _handle_set_team(cmd: Command, owner: str, repo: str, ghsa_id: str) -> CommandResult:
    """Handle set-team command.

    Args:
        cmd: Parsed command
        owner: Repository owner
        repo: Repository name
        ghsa_id: GHSA identifier

    Returns:
        CommandResult with team notification confirmation
    """
    if not cmd.arguments:
        return CommandResult(
            success=False,
            message=(
                "❌ **Error:** Missing team identifier\n\nUsage: `set-team <team>`\n\nExample: `set-team python/psrt`"
            ),
        )

    team = cmd.arguments[0]

    if "/" not in team:
        return CommandResult(
            success=False,
            message=(
                f"❌ **Error:** Invalid team format: '{team}'\n\n"
                f"Team must be in format `org/team` (e.g., `python/psrt`)"
            ),
        )

    try:
        state_manager = StateManager()
        ghsa_state = state_manager.get_ghsa_state(f"{owner}/{repo}/{ghsa_id}")
        ghsa_state.notification_team = team
        state_manager.save()

        message = (
            f"👥 **Notification Team Set**\n\n"
            f"**Advisory:** {ghsa_id}\n"
            f"**Team:** @{team}\n\n"
            f"This team will be mentioned in inactivity reminder notifications."
        )

        return CommandResult(success=True, message=message)

    except Exception as e:
        return CommandResult(
            success=False,
            message=f"❌ **Error:** Failed to set notification team: {e!s}",
            error=e,
        )
