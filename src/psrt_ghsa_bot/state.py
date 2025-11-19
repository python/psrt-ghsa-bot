"""State management for tracking processed comments and commands.

We don't continuosly run the playwright process, we run it periodiclly in GHA.
So, we need a state tracking to keep track of the last time we ran the GHA
so we only process comments for GHSA things that have been created AT or
AFTER the last tiem we ran.

We could do a simple file based thing touching an epoch a reading it
but this tries to rely on gha cache to make it a little faster.

- we store the state in a file in the cache directory
- we use the cache directory to store the state file
- state file contains json obj with state including:
  - date/time we last ran
  - last comment id we processed
  - set of commands we've processed
  - count of commands processed
- we use the state file to determine what to process afterwards
- update stat efile AFTER processing this new set
- 🔁
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class GHSAState:
    """State for a single GHSA."""

    last_comment_id: str | None = None
    last_processed_at: str | None = None
    processed_commands: set[str] = field(default_factory=set)
    commands_processed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "last_comment_id": self.last_comment_id,
            "last_processed_at": self.last_processed_at,
            "processed_commands": list(self.processed_commands),
            "commands_processed_count": self.commands_processed_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GHSAState:
        """Creat from dict."""
        return cls(
            last_comment_id=data.get("last_comment_id"),
            last_processed_at=data.get("last_processed_at"),
            processed_commands=set(data.get("processed_commands", [])),
            commands_processed_count=data.get("commands_processed_count", 0),
        )


@dataclass
class BotState:
    """Global bot state."""

    last_run: str | None = None
    ghsas: dict[str, GHSAState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "last_run": self.last_run,
            "ghsas": {key: state.to_dict() for key, state in self.ghsas.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BotState:
        """Create from dict."""
        return cls(
            last_run=data.get("last_run"),
            ghsas={key: GHSAState.from_dict(value) for key, value in data.get("ghsas", {}).items()},
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
                with open(self.state_file) as f:
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
        with open(self.state_file, "w") as f:
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

    def is_command_processed(self, ghsa_id: str, comment_id: str, command_text: str, author: str) -> bool:
        """Check if a command has been processed.

        TODO: so, if someone edits their comment will it change the hasH?

        Args:
            ghsa_id: GHSA identifier
            comment_id: GitHub comment ID
            command_text: Raw command text
            author: Comment author username

        Returns:
            True if command was already processed
        """
        ghsa_state = self.get_ghsa_state(ghsa_id)
        command_hash = self._hash_command(comment_id, command_text, author)
        return command_hash in ghsa_state.processed_commands

    def mark_command_processed(self, ghsa_id: str, comment_id: str, command_text: str, author: str) -> None:
        """Mark a command as processed.

        Args:
            ghsa_id: GHSA identifier
            comment_id: GitHub comment ID
            command_text: Raw command text
            author: Comment author username
        """
        ghsa_state = self.get_ghsa_state(ghsa_id)
        command_hash = self._hash_command(comment_id, command_text, author)
        ghsa_state.processed_commands.add(command_hash)
        ghsa_state.commands_processed_count += 1
        ghsa_state.last_comment_id = comment_id
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()

    def _hash_command(self, comment_id: str, command_text: str, author: str) -> str:
        """Generate unique hash for a command.

        Args:
            comment_id: GitHub comment ID
            command_text: Raw command text
            author: Comment author username

        Returns:
            SHA-256 hash of command components
        """
        content = f"{comment_id}:{command_text}:{author}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def update_ghsa_state(self, ghsa_id: str, last_comment_id: str | None = None) -> None:
        """Update state for a GHSA after processing.

        Args:
            ghsa_id: GHSA identifier
            last_comment_id: Last processed comment ID
        """
        ghsa_state = self.get_ghsa_state(ghsa_id)
        if last_comment_id:
            ghsa_state.last_comment_id = last_comment_id
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()
