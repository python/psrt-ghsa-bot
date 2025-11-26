"""Milestone-based reminder system for GHSA advisories.

Reminders are sent based on advisory age relative to the deadline.
For example, with DEADLINE_DAYS=90 and DEADLINE_REMINDER_DAYS=[60,30,15,7,3,1],
reminders are sent when there are 60, 30, 15, 7, 3, and 1 days remaining.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from psrt_ghsa_bot.polyfills.comments.post_comment import post_ghsa_comment
from psrt_ghsa_bot.settings import settings

if TYPE_CHECKING:
    from githubkit import GitHub

    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient
    from psrt_ghsa_bot.state import GHSAState, StateManager


logger = logging.getLogger(__name__)


def get_days_until_deadline(created_at_str: str, current_time: datetime) -> int:
    """Calculate days remaining until deadline.

    Args:
        created_at_str: ISO 8601 timestamp of advisory creation
        current_time: Current time for comparison

    Returns:
        Days until deadline (negative if past deadline)
    """
    created_at = datetime.fromisoformat(created_at_str)
    advisory_age_days = (current_time - created_at).days
    return settings.reminders.DEADLINE_DAYS - advisory_age_days


def get_pending_reminder_day(
    ghsa_state: GHSAState,
    days_until_deadline: int,
) -> int | None:
    """Check if a milestone reminder should be sent.

    Args:
        ghsa_state: State object for the advisory
        days_until_deadline: Days remaining until deadline

    Returns:
        The milestone day to remind for, or None if no reminder needed
    """
    for milestone_day in settings.reminders.DEADLINE_REMINDER_DAYS:
        if days_until_deadline <= milestone_day and milestone_day not in ghsa_state.reminders_sent_at_days:
            return milestone_day
    return None


def format_reminder_message(
    ghsa_id: str,
    days_until_deadline: int,
) -> str:
    """Format the reminder comment message.

    Args:
        ghsa_id: GHSA identifier
        days_until_deadline: Days remaining until deadline

    Returns:
        Formatted markdown message
    """
    team = settings.reminders.DEFAULT_NOTIFICATION_TEAM

    if days_until_deadline <= 0:
        urgency = "🚨 **DEADLINE REACHED**"
        deadline_msg = "The 90-day deadline has been reached!"
    elif days_until_deadline == 1:
        urgency = "🚨 **URGENT**"
        deadline_msg = "The deadline is **tomorrow**!"
    elif days_until_deadline <= settings.reminders.URGENT_DAYS_THRESHOLD:
        urgency = "⚠️ **WARNING**"
        deadline_msg = f"Only **{days_until_deadline} days** remain until the deadline!"
    else:
        urgency = "⏰ **Reminder**"
        deadline_msg = f"**{days_until_deadline} days** remain until the 90-day deadline."

    return (
        f"{urgency}: Advisory Deadline Approaching\n\n"
        f"@{team}\n\n"
        f"**Advisory:** {ghsa_id}\n"
        f"{deadline_msg}\n\n"
        f"**Action Required:**\n"
        f"- Review the advisory status\n"
        f"- Post an update or comment to indicate progress\n"
        f"- Use bot commands to manage CVE assignment or publication"
    )


def check_and_send_reminders(
    github: GitHub,
    playwright_client: GitHubPlaywrightClient,
    advisories: list[dict],
    state_manager: StateManager,
) -> int:
    """Check all active advisories and send milestone reminders if needed.

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
        repository = advisory.get("repository")
        if not repository or not repository.get("full_name"):
            logger.error("Advisory %s has no repository, skipping", ghsa_id)
            continue
        owner, repo = repository["full_name"].split("/", 1)
        ghsa_key = f"{owner}/{repo}/{ghsa_id}"

        ghsa_state = state_manager.get_ghsa_state(ghsa_key)

        try:
            days_until_deadline = get_days_until_deadline(advisory["created_at"], current_time)
            milestone_day = get_pending_reminder_day(ghsa_state, days_until_deadline)

            if milestone_day is None:
                continue

            logger.info(
                "Sending %d-day reminder for %s (%d days remaining)",
                milestone_day,
                ghsa_key,
                days_until_deadline,
            )

            message = format_reminder_message(ghsa_id, days_until_deadline)

            post_ghsa_comment(playwright_client, owner, repo, ghsa_id, message)

            ghsa_state.reminders_sent_at_days.add(milestone_day)
            state_manager.save()

            reminders_sent += 1

        except Exception:
            logger.exception("Failed to process reminder for %s", ghsa_key)
            continue

    return reminders_sent
