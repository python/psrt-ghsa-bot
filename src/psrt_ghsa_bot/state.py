"""State management for tracking processed comments and commands.

We don't continuously run the playwright process, we run it periodically in GHA.
So, we need state tracking to keep track of the last time we ran so we only
process comments that have been created AFTER the last time we ran.

Instead of storing all processed command hashes (which grows unbounded),
we use timestamp-based filtering:
- Store `last_processed_at` per GHSA
- Only process comments newer than this timestamp
- For replay capability, add comment IDs to `commands_to_reprocess`
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class GHSAState:
    """State for a single GHSA."""

    last_processed_at: str | None = None
    commands_processed_count: int = 0
    last_activity_at: str | None = None
    deadline_days: int | None = None
    warning_threshold_days: int | None = None
    notification_team: str | None = None
    last_reminder_sent_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "last_processed_at": self.last_processed_at,
            "commands_processed_count": self.commands_processed_count,
            "last_activity_at": self.last_activity_at,
            "deadline_days": self.deadline_days,
            "warning_threshold_days": self.warning_threshold_days,
            "notification_team": self.notification_team,
            "last_reminder_sent_at": self.last_reminder_sent_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Creat from dict."""
        return cls(
            last_processed_at=data.get("last_processed_at"),
            commands_processed_count=data.get("commands_processed_count", 0),
            last_activity_at=data.get("last_activity_at"),
            deadline_days=data.get("deadline_days"),
            warning_threshold_days=data.get("warning_threshold_days"),
            notification_team=data.get("notification_team"),
            last_reminder_sent_at=data.get("last_reminder_sent_at"),
        )


@dataclass
class BotState:
    """Global bot state."""

    last_run: str | None = None
    ghsas: dict[str, GHSAState] = field(default_factory=dict)
    commands_to_reprocess: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "last_run": self.last_run,
            "ghsas": {key: state.to_dict() for key, state in self.ghsas.items()},
            "commands_to_reprocess": self.commands_to_reprocess,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Create from dict."""
        return cls(
            last_run=data.get("last_run"),
            ghsas={key: GHSAState.from_dict(value) for key, value in data.get("ghsas", {}).items()},
            commands_to_reprocess=data.get("commands_to_reprocess", []),
        )


class StateManager:
    """Manages bot state with GHA cache + git storage."""

    def __init__(self, state_file: Path | None = None) -> None:
        """Initialize state manager.

        Args:
            state_file: Path to state file. Defaults to repo root state.json
        """
        self.state_file = state_file or Path(__file__).parent.parent.parent / "state.json"
        self._state: BotState | None = None

    def load(self) -> BotState:
        """Load state from file or create new."""
        if self._state is not None:
            return self._state

        if self.state_file.exists():
            try:
                with self.state_file.open() as f:
                    data = json.load(f)
                self._state = BotState.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                self._state = BotState()
        else:
            self._state = BotState()

        return self._state

    def save(self) -> None:
        """Save state to file."""
        if self._state is None:
            return

        self._state.last_run = datetime.now(UTC).isoformat()

        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w") as f:
            json.dump(self._state.to_dict(), f, indent=2)

    def get_ghsa_state(self, ghsa_id: str) -> GHSAState:
        """Get or create state for a GHSA.

        Args:
            ghsa_id: GHSA identifier (e.g., "python/cpython/GHSA-xxxx-xxxx-xxxx")

        Returns:
            GHSAState for the given GHSA
        """
        state = self.load()
        if ghsa_id not in state.ghsas:
            state.ghsas[ghsa_id] = GHSAState()
        return state.ghsas[ghsa_id]

    def should_process_comment(self, ghsa_id: str, comment_id: str, comment_created_at: datetime) -> bool:
        """Check if a comment should be processed based on timestamp.

        Args:
            ghsa_id: GHSA identifier
            comment_id: GitHub comment ID
            comment_created_at: When the comment was created

        Returns:
            True if comment should be processed (newer than last run or in reprocess list)
        """
        state = self.load()

        if comment_id in state.commands_to_reprocess:
            return True

        ghsa_state = self.get_ghsa_state(ghsa_id)
        if ghsa_state.last_processed_at is None:
            return True

        last_processed = datetime.fromisoformat(ghsa_state.last_processed_at)
        return comment_created_at > last_processed

    def mark_command_processed(self, ghsa_id: str, comment_id: str) -> None:
        """Mark a command as processed.

        Args:
            ghsa_id: GHSA identifier
            comment_id: GitHub comment ID
        """
        state = self.load()
        ghsa_state = self.get_ghsa_state(ghsa_id)
        ghsa_state.commands_processed_count += 1
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()

        if comment_id in state.commands_to_reprocess:
            state.commands_to_reprocess.remove(comment_id)

    def update_ghsa_state(self, ghsa_id: str) -> None:
        """Update state for a GHSA after processing.

        Args:
            ghsa_id: GHSA identifier
        """
        ghsa_state = self.get_ghsa_state(ghsa_id)
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()

    def add_command_to_reprocess(self, comment_id: str) -> None:
        """Add a comment ID to the reprocess list.

        This allows replaying commands by adding their comment IDs
        via a PR to the state file.

        Args:
            comment_id: GitHub comment ID to reprocess
        """
        state = self.load()
        if comment_id not in state.commands_to_reprocess:
            state.commands_to_reprocess.append(comment_id)

    def get_commands_to_reprocess(self) -> list[str]:
        """Get list of comment IDs pending reprocessing.

        Returns:
            List of comment IDs to reprocess
        """
        return self.load().commands_to_reprocess.copy()
