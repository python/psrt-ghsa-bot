"""Tests for state management."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from psrt_ghsa_bot.state import BotState, GHSAState, StateManager


def test_ghsa_state_to_dict() -> None:
    state = GHSAState(
        last_comment_id="comment-123",
        last_processed_at="2025-11-19T12:00:00Z",
        processed_commands={"hash1", "hash2"},
        commands_processed_count=2,
    )

    data = state.to_dict()

    assert data["last_comment_id"] == "comment-123"
    assert data["last_processed_at"] == "2025-11-19T12:00:00Z"
    assert set(data["processed_commands"]) == {"hash1", "hash2"}
    assert data["commands_processed_count"] == 2


def test_ghsa_state_from_dict() -> None:
    data = {
        "last_comment_id": "comment-123",
        "last_processed_at": "2025-11-19T12:00:00Z",
        "processed_commands": ["hash1", "hash2"],
        "commands_processed_count": 2,
    }

    state = GHSAState.from_dict(data)

    assert state.last_comment_id == "comment-123"
    assert state.last_processed_at == "2025-11-19T12:00:00Z"
    assert state.processed_commands == {"hash1", "hash2"}
    assert state.commands_processed_count == 2


def test_bot_state_to_dict() -> None:
    bot_state = BotState(
        last_run="2025-11-19T12:00:00Z",
        ghsas={
            "python/cpython/GHSA-xxxx": GHSAState(
                last_comment_id="comment-123",
                processed_commands={"hash1"},
                commands_processed_count=1,
            )
        },
    )

    data = bot_state.to_dict()

    assert data["last_run"] == "2025-11-19T12:00:00Z"
    assert "python/cpython/GHSA-xxxx" in data["ghsas"]
    assert data["ghsas"]["python/cpython/GHSA-xxxx"]["last_comment_id"] == "comment-123"


def test_bot_state_from_dict() -> None:
    data = {
        "last_run": "2025-11-19T12:00:00Z",
        "ghsas": {
            "python/cpython/GHSA-xxxx": {
                "last_comment_id": "comment-123",
                "last_processed_at": None,
                "processed_commands": ["hash1"],
                "commands_processed_count": 1,
            }
        },
    }

    bot_state = BotState.from_dict(data)

    assert bot_state.last_run == "2025-11-19T12:00:00Z"
    assert "python/cpython/GHSA-xxxx" in bot_state.ghsas
    assert bot_state.ghsas["python/cpython/GHSA-xxxx"].last_comment_id == "comment-123"


def test_state_manager_load_empty() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        state = manager.load()

        assert state.last_run is None
        assert len(state.ghsas) == 0


def test_state_manager_save_and_load() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        state = manager.load()
        state.ghsas["python/cpython/GHSA-xxxx"] = GHSAState(last_comment_id="comment-123")

        manager.save()

        with Path.open(state_file) as f:
            data = json.load(f)

        assert "python/cpython/GHSA-xxxx" in data["ghsas"]
        assert data["ghsas"]["python/cpython/GHSA-xxxx"]["last_comment_id"] == "comment-123"


def test_state_manager_get_ghsa_state() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")

        assert ghsa_state.last_comment_id is None
        assert len(ghsa_state.processed_commands) == 0


def test_state_manager_is_command_processed() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        is_processed = manager.is_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot help",
            "octocat",
        )

        assert not is_processed


def test_state_manager_mark_command_processed() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.mark_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot help",
            "octocat",
        )

        is_processed = manager.is_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot help",
            "octocat",
        )

        assert is_processed


def test_state_manager_command_hash_different_for_different_inputs() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.mark_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot help",
            "octocat",
        )

        is_processed_different_comment = manager.is_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-456",
            "@bot help",
            "octocat",
        )
        assert not is_processed_different_comment

        is_processed_different_command = manager.is_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot status",
            "octocat",
        )
        assert not is_processed_different_command

        is_processed_different_author = manager.is_command_processed(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            "@bot help",
            "different-user",
        )
        assert not is_processed_different_author


def test_state_manager_update_ghsa_state() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.update_ghsa_state(
            "python/cpython/GHSA-xxxx",
            last_comment_id="comment-999",
        )

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")

        assert ghsa_state.last_comment_id == "comment-999"
        assert ghsa_state.last_processed_at is not None
