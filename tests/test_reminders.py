"""Tests for inactivity reminder system."""

from datetime import UTC, datetime, timedelta

from psrt_ghsa_bot.reminders import (
    calculate_deadline,
    format_reminder_message,
    should_send_reminder,
)
from psrt_ghsa_bot.state import GHSAState


def test_calculate_deadline_default() -> None:
    created_at = "2025-01-01T00:00:00Z"
    deadline = calculate_deadline(created_at, None)

    expected = datetime.fromisoformat(created_at) + timedelta(days=90)
    assert deadline == expected


def test_calculate_deadline_custom() -> None:
    created_at = "2025-01-01T00:00:00Z"
    deadline = calculate_deadline(created_at, 60)

    expected = datetime.fromisoformat(created_at) + timedelta(days=60)
    assert deadline == expected


def test_should_send_reminder_within_threshold() -> None:
    state = GHSAState()
    state.last_activity_at = "2025-01-01T00:00:00Z"
    state.deadline_days = 30
    state.warning_threshold_days = 14

    created_at = "2025-01-01T00:00:00Z"
    current_time = datetime(2025, 1, 20, tzinfo=UTC)

    should_send, days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is True
    assert days_remaining == 11


def test_should_send_reminder_outside_threshold() -> None:
    state = GHSAState()
    state.last_activity_at = "2025-01-01T00:00:00Z"
    state.deadline_days = 90
    state.warning_threshold_days = 14

    created_at = "2025-01-01T00:00:00Z"
    current_time = datetime(2025, 1, 15, tzinfo=UTC)

    should_send, days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is False
    assert days_remaining == 76


def test_should_send_reminder_recent_activity() -> None:
    state = GHSAState()
    state.deadline_days = 30
    state.warning_threshold_days = 14

    created_at = "2025-01-01T00:00:00Z"
    state.last_activity_at = "2025-01-18T00:00:00Z"
    current_time = datetime(2025, 1, 20, tzinfo=UTC)

    should_send, days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is False
    assert days_remaining == 11


def test_should_send_reminder_no_activity() -> None:
    state = GHSAState()
    state.deadline_days = 30
    state.warning_threshold_days = 14

    created_at = "2025-01-01T00:00:00Z"
    current_time = datetime(2025, 1, 20, tzinfo=UTC)

    should_send, days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is True
    assert days_remaining == 11


def test_should_send_reminder_recent_reminder() -> None:
    state = GHSAState()
    state.deadline_days = 30
    state.warning_threshold_days = 14
    state.last_activity_at = "2025-01-01T00:00:00Z"
    state.last_reminder_sent_at = "2025-01-19T23:00:00Z"

    created_at = "2025-01-01T00:00:00Z"
    current_time = datetime(2025, 1, 20, 0, 30, 0, tzinfo=UTC)

    should_send, _days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is False


def test_should_send_reminder_past_deadline() -> None:
    state = GHSAState()
    state.deadline_days = 30
    state.warning_threshold_days = 14

    created_at = "2025-01-01T00:00:00Z"
    current_time = datetime(2025, 2, 15, tzinfo=UTC)

    should_send, days_remaining = should_send_reminder(state, created_at, current_time)

    assert should_send is False
    assert days_remaining < 0


def test_format_reminder_message_urgent_today() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 0, 14, "python/psrt")

    assert "🚨 **URGENT**" in message
    assert "today" in message
    assert "@python/psrt" in message
    assert "GHSA-xxxx-xxxx-xxxx" in message


def test_format_reminder_message_urgent_tomorrow() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 1, 14, "python/psrt")

    assert "🚨 **URGENT**" in message
    assert "tomorrow" in message


def test_format_reminder_message_warning_week() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 5, 14, "python/psrt")

    assert "⚠️ **WARNING**" in message
    assert "5 days" in message


def test_format_reminder_message_normal() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 20, 10, "python/psrt")

    assert "⏰ **Reminder**" in message
    assert "20 days" in message


def test_format_reminder_message_custom_team() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 10, 14, "security/team")

    assert "@security/team" in message


def test_format_reminder_message_no_activity() -> None:
    message = format_reminder_message("GHSA-xxxx-xxxx-xxxx", 10, None, "python/psrt")

    assert "14 days" not in message
