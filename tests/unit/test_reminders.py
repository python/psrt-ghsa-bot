"""Tests for the milestone-based reminder system."""

from datetime import UTC, datetime, timedelta

from psrt_ghsa_bot.reminders import (
    format_reminder_message,
    get_days_until_deadline,
    get_pending_reminder_day,
)
from psrt_ghsa_bot.state import GHSAState


def test_get_days_until_deadline_new_advisory() -> None:
    created_at = datetime.now(UTC).isoformat()
    current_time = datetime.now(UTC)
    days_until = get_days_until_deadline(created_at, current_time)
    assert days_until == 90


def test_get_days_until_deadline_30_days_old() -> None:
    created_at = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    current_time = datetime.now(UTC)
    days_until = get_days_until_deadline(created_at, current_time)
    assert days_until == 60


def test_get_days_until_deadline_past_deadline() -> None:
    created_at = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    current_time = datetime.now(UTC)
    days_until = get_days_until_deadline(created_at, current_time)
    assert days_until == -10


def test_get_pending_reminder_day_no_reminders_sent() -> None:
    state = GHSAState()
    milestone_day = get_pending_reminder_day(state, days_until_deadline=55)
    assert milestone_day == 60


def test_get_pending_reminder_day_60_already_sent() -> None:
    state = GHSAState()
    state.reminders_sent_at_days.add(60)
    milestone_day = get_pending_reminder_day(state, days_until_deadline=55)
    assert milestone_day is None


def test_get_pending_reminder_day_crosses_30_milestone() -> None:
    state = GHSAState()
    state.reminders_sent_at_days.add(60)
    milestone_day = get_pending_reminder_day(state, days_until_deadline=25)
    assert milestone_day == 30


def test_get_pending_reminder_day_all_sent() -> None:
    state = GHSAState()
    state.reminders_sent_at_days = {60, 30, 15, 7, 3, 1}
    milestone_day = get_pending_reminder_day(state, days_until_deadline=0)
    assert milestone_day is None


def test_get_pending_reminder_day_urgent() -> None:
    state = GHSAState()
    state.reminders_sent_at_days = {60, 30, 15, 7}
    milestone_day = get_pending_reminder_day(state, days_until_deadline=2)
    assert milestone_day == 3


def test_get_pending_reminder_day_not_yet_in_window() -> None:
    state = GHSAState()
    milestone_day = get_pending_reminder_day(state, days_until_deadline=85)
    assert milestone_day is None


def test_format_reminder_message_deadline_reached() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 0)
    assert "DEADLINE REACHED" in message
    assert "GHSA-xxxx-xxxx-xxxx" in message
    assert "@python/psrt" in message


def test_format_reminder_message_tomorrow() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 1)
    assert "URGENT" in message
    assert "tomorrow" in message


def test_format_reminder_message_urgent_week() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 5)
    assert "WARNING" in message
    assert "5 days" in message


def test_format_reminder_message_normal() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 30)
    assert "Reminder" in message
    assert "30 days" in message
    assert "@python/psrt" in message


def test_format_reminder_message_contains_action_items() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 15)
    assert "Action Required" in message
    assert "Review the advisory status" in message
