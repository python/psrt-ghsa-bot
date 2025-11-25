"""Tests for state management."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from psrt_ghsa_bot.state import BotState, GHSAState, StateManager


def test_ghsa_state_to_dict() -> None:
    state = GHSAState(
        last_processed_at="2025-11-19T12:00:00Z",
        commands_processed_count=2,
    )

    data = state.to_dict()

    assert data["last_processed_at"] == "2025-11-19T12:00:00Z"
    assert data["commands_processed_count"] == 2


def test_ghsa_state_from_dict() -> None:
    data = {
        "last_processed_at": "2025-11-19T12:00:00Z",
        "commands_processed_count": 2,
    }

    state = GHSAState.from_dict(data)

    assert state.last_processed_at == "2025-11-19T12:00:00Z"
    assert state.commands_processed_count == 2


def test_bot_state_to_dict() -> None:
    bot_state = BotState(
        last_run="2025-11-19T12:00:00Z",
        ghsas={
            "python/cpython/GHSA-xxxx": GHSAState(
                last_processed_at="2025-11-19T11:00:00Z",
                commands_processed_count=1,
            )
        },
        commands_to_reprocess=["comment-abc"],
    )

    data = bot_state.to_dict()

    assert data["last_run"] == "2025-11-19T12:00:00Z"
    assert "python/cpython/GHSA-xxxx" in data["ghsas"]
    assert data["ghsas"]["python/cpython/GHSA-xxxx"]["last_processed_at"] == "2025-11-19T11:00:00Z"
    assert data["commands_to_reprocess"] == ["comment-abc"]


def test_bot_state_from_dict() -> None:
    data = {
        "last_run": "2025-11-19T12:00:00Z",
        "ghsas": {
            "python/cpython/GHSA-xxxx": {
                "last_processed_at": "2025-11-19T11:00:00Z",
                "commands_processed_count": 1,
            }
        },
        "commands_to_reprocess": ["comment-abc"],
    }

    bot_state = BotState.from_dict(data)

    assert bot_state.last_run == "2025-11-19T12:00:00Z"
    assert "python/cpython/GHSA-xxxx" in bot_state.ghsas
    assert bot_state.ghsas["python/cpython/GHSA-xxxx"].last_processed_at == "2025-11-19T11:00:00Z"
    assert bot_state.commands_to_reprocess == ["comment-abc"]


def test_state_manager_load_empty() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        state = manager.load()

        assert state.last_run is None
        assert len(state.ghsas) == 0
        assert state.commands_to_reprocess == []


def test_state_manager_save_and_load() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        state = manager.load()
        state.ghsas["python/cpython/GHSA-xxxx"] = GHSAState(last_processed_at="2025-11-19T12:00:00Z")

        manager.save()

        with Path.open(state_file) as f:
            data = json.load(f)

        assert "python/cpython/GHSA-xxxx" in data["ghsas"]
        assert data["ghsas"]["python/cpython/GHSA-xxxx"]["last_processed_at"] == "2025-11-19T12:00:00Z"


def test_state_manager_get_ghsa_state() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")

        assert ghsa_state.last_processed_at is None
        assert ghsa_state.commands_processed_count == 0


def test_state_manager_should_process_comment_new_ghsa() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        should_process = manager.should_process_comment(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            datetime.now(UTC),
        )

        assert should_process


def test_state_manager_should_process_comment_newer_than_last() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")
        ghsa_state.last_processed_at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

        should_process = manager.should_process_comment(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            datetime.now(UTC),
        )

        assert should_process


def test_state_manager_should_not_process_older_comment() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()

        old_comment_time = datetime.now(UTC) - timedelta(hours=1)
        should_process = manager.should_process_comment(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            old_comment_time,
        )

        assert not should_process


def test_state_manager_should_process_comment_in_reprocess_list() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")
        ghsa_state.last_processed_at = datetime.now(UTC).isoformat()

        manager.add_command_to_reprocess("comment-123")

        old_comment_time = datetime.now(UTC) - timedelta(hours=1)
        should_process = manager.should_process_comment(
            "python/cpython/GHSA-xxxx",
            "comment-123",
            old_comment_time,
        )

        assert should_process


def test_state_manager_mark_command_processed() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.mark_command_processed("python/cpython/GHSA-xxxx", "comment-123")

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")
        assert ghsa_state.commands_processed_count == 1
        assert ghsa_state.last_processed_at is not None


def test_state_manager_mark_command_removes_from_reprocess() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.add_command_to_reprocess("comment-123")
        assert "comment-123" in manager.get_commands_to_reprocess()

        manager.mark_command_processed("python/cpython/GHSA-xxxx", "comment-123")

        assert "comment-123" not in manager.get_commands_to_reprocess()


def test_state_manager_update_ghsa_state() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.update_ghsa_state("python/cpython/GHSA-xxxx")

        ghsa_state = manager.get_ghsa_state("python/cpython/GHSA-xxxx")
        assert ghsa_state.last_processed_at is not None


def test_state_manager_add_command_to_reprocess() -> None:
    with TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        manager = StateManager(state_file)

        manager.add_command_to_reprocess("comment-123")
        manager.add_command_to_reprocess("comment-456")
        manager.add_command_to_reprocess("comment-123")

        reprocess_list = manager.get_commands_to_reprocess()
        assert reprocess_list == ["comment-123", "comment-456"]
