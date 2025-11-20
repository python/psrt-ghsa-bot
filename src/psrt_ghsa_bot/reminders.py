"""Inactivity reminder system for GHSA advisories approaching deadlines."""

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from psrt_ghsa_bot.polyfills.comments.post_comment import post_ghsa_comment

if TYPE_CHECKING:
    from githubkit import GitHub

    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient
    from psrt_ghsa_bot.state import GHSAState, StateManager


logger = logging.getLogger(__name__)

# TODO: should just move from here and .env to settings.py along with some other
# keys that can be public
DEFAULT_DEADLINE_DAYS = 90
"""Deadline for activity needed on an advisory in days."""
DEFAULT_WARNING_THRESHOLD_DAYS = 14
"""When to start sending warnings about approaching deadlines in days."""
HOURS_BETWEEN_REMINDERS = 23
"""Minimum hours between daily reminders."""
URGENT_DAYS_THRESHOLD = 7
"""Days threshold for urgent warnings."""


def get_default_notification_team() -> str:
    """Get the default notification team from environment variables."""
    return os.environ.get("DEFAULT_NOTIFICATION_TEAM", "python/psrt")


def calculate_deadline(created_at_str: str, deadline_days: int | None) -> datetime:
    """Calculate deadline for an advisory.

    Args:
        created_at_str: ISO 8601 timestamp of advisory creation
        deadline_days: Custom deadline in days, or None for default (90 days)

    Returns:
        Deadline datetime
    """
    created_at = datetime.fromisoformat(created_at_str)
    days = deadline_days if deadline_days is not None else DEFAULT_DEADLINE_DAYS
    return created_at + timedelta(days=days)


def should_send_reminder(
    ghsa_state: GHSAState,
    advisory_created_at: str,
    current_time: datetime,
) -> tuple[bool, int]:
    """Check if an inactivity reminder should be sent.

    Args:
        ghsa_state: State object for the advisory
        advisory_created_at: ISO 8601 timestamp of advisory creation
        current_time: Current time for comparison

    Returns:
        Tuple of (should_send, days_until_deadline)
    """
    deadline = calculate_deadline(advisory_created_at, ghsa_state.deadline_days)
    days_until_deadline = (deadline - current_time).days

    if days_until_deadline < 0:
        return False, days_until_deadline

    warning_threshold = (
        ghsa_state.warning_threshold_days
        if ghsa_state.warning_threshold_days is not None
        else DEFAULT_WARNING_THRESHOLD_DAYS
    )

    if days_until_deadline > warning_threshold:
        return False, days_until_deadline

    if ghsa_state.last_activity_at is None:
        return True, days_until_deadline

    last_activity = datetime.fromisoformat(ghsa_state.last_activity_at)
    days_since_activity = (current_time - last_activity).days

    if days_since_activity < warning_threshold:
        return False, days_until_deadline

    if ghsa_state.last_reminder_sent_at is not None:
        last_reminder = datetime.fromisoformat(ghsa_state.last_reminder_sent_at)
        hours_since_reminder = (current_time - last_reminder).total_seconds() / 3600
        if hours_since_reminder < HOURS_BETWEEN_REMINDERS:
            return False, days_until_deadline

    return True, days_until_deadline


def format_reminder_message(
    ghsa_id: str,
    days_until_deadline: int,
    days_since_activity: int | None,
    notification_team: str | None,
) -> str:
    """Format the reminder comment message.

    Args:
        ghsa_id: GHSA identifier
        days_until_deadline: Number of days remaining until deadline
        days_since_activity: Number of days since last activity, or None
        notification_team: Team to mention, or None for default

    Returns:
        Formatted markdown message
    """
    team = notification_team if notification_team is not None else get_default_notification_team()

    if days_until_deadline == 0:
        urgency = "🚨 **URGENT**"
        deadline_msg = "The deadline is **today**!"
    elif days_until_deadline == 1:
        urgency = "🚨 **URGENT**"
        deadline_msg = "The deadline is **tomorrow**!"
    elif days_until_deadline <= URGENT_DAYS_THRESHOLD:
        urgency = "⚠️ **WARNING**"
        deadline_msg = f"Only **{days_until_deadline} days** remain until the deadline!"
    else:
        urgency = "⏰ **Reminder**"
        deadline_msg = f"**{days_until_deadline} days** remain until the deadline."

    activity_msg = ""
    if days_since_activity is not None and days_since_activity > 0:
        activity_msg = f"\n\nThis advisory has had no activity for **{days_since_activity} days**."

    return (
        f"{urgency}: Inactivity Deadline Approaching\n\n"
        f"@{team}\n\n"
        f"**Advisory:** {ghsa_id}\n"
        f"{deadline_msg}{activity_msg}\n\n"
        f"**Action Required:**\n"
        f"- Review the advisory status\n"
        f"- Post an update or comment to indicate progress\n"
        f"- Use bot commands to manage CVE assignment or publication\n\n"
        f"_This reminder will continue daily until activity is detected or the deadline is reached._"
    )


def check_and_send_reminders(
    github: GitHub,
    playwright_client: GitHubPlaywrightClient,
    advisories: list[dict],
    state_manager: StateManager,
) -> int:
    """Check all active advisories and send reminders if needed.

    Args:
        github: GitHub API client
        playwright_client: Playwright client for posting comments
        advisories: List of advisory dictionaries from GitHub API
        state_manager: State manager instance

    Returns:
        Number of reminders sent
    """
    current_time = datetime.now(UTC)
    reminders_sent = 0

    for advisory in advisories:
        ghsa_id = advisory["ghsa_id"]
        owner, repo = advisory.get("repository", {}).get("full_name", "/").split("/", 1)
        ghsa_key = f"{owner}/{repo}/{ghsa_id}"

        ghsa_state = state_manager.get_ghsa_state(ghsa_key)

        try:
            should_send, days_until_deadline = should_send_reminder(
                ghsa_state,
                advisory["created_at"],
                current_time,
            )

            if not should_send:
                continue

            days_since_activity = None
            if ghsa_state.last_activity_at is not None:
                last_activity = datetime.fromisoformat(ghsa_state.last_activity_at)
                days_since_activity = (current_time - last_activity).days

            message = format_reminder_message(
                ghsa_id,
                days_until_deadline,
                days_since_activity,
                ghsa_state.notification_team,
            )

            post_ghsa_comment(
                playwright_client,
                owner,
                repo,
                ghsa_id,
                message,
            )

            ghsa_state.last_reminder_sent_at = current_time.isoformat()
            state_manager.save()

            logger.info(
                "Sent reminder for %s (%d days until deadline)",
                ghsa_key,
                days_until_deadline,
            )
            reminders_sent += 1

        except Exception:
            logger.exception("Failed to process reminder for %s", ghsa_key)
            continue

    return reminders_sent
