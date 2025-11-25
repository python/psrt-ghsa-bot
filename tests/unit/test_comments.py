"""Unit tests for GHSA comment functionality."""

from datetime import datetime

import pytest

from psrt_ghsa_bot.polyfills import (
    GHSAComment,
    GitHubPlaywrightClient,
    post_ghsa_comment,
)


def test_ghsa_comment_dataclass_repr() -> None:
    """Test the GHSAComment repr method."""
    comment = GHSAComment(
        id="123",
        author="testuser",
        body="Test comment",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        is_bot_comment=False,
    )

    repr_str = repr(comment)
    assert "GHSAComment" in repr_str
    assert "id=123" in repr_str
    assert "author=testuser" in repr_str
    assert "2024-01-01 12:00:00" in repr_str


def test_ghsa_comment_dataclass_fields() -> None:
    """Test that GHSAComment has all required fields."""
    comment = GHSAComment(
        id="test-id-123",
        author="octocat",
        body="This is a test comment body",
        created_at=datetime(2024, 1, 15, 10, 30, 0),
        updated_at=datetime(2024, 1, 15, 11, 0, 0),
        is_bot_comment=False,
    )

    assert comment.id == "test-id-123"
    assert comment.author == "octocat"
    assert comment.body == "This is a test comment body"
    assert comment.created_at == datetime(2024, 1, 15, 10, 30, 0)
    assert comment.updated_at == datetime(2024, 1, 15, 11, 0, 0)
    assert comment.is_bot_comment is False


def test_post_comment_empty_body_error() -> None:
    """Test that posting an empty comment raises ValueError."""
    client = GitHubPlaywrightClient(headless=True)
    with pytest.raises(ValueError, match="comment_body cannot be empty"):
        post_ghsa_comment(
            client,
            owner="jolt-org",
            repo="ghsa-testing",
            ghsa_id="GHSA-f3x5-4pp6-r2mf",
            comment_body="",
        )


def test_post_comment_whitespace_only_error() -> None:
    """Test that posting whitespace-only comment raises ValueError."""
    client = GitHubPlaywrightClient(headless=True)
    with pytest.raises(ValueError, match="comment_body cannot be empty"):
        post_ghsa_comment(
            client,
            owner="jolt-org",
            repo="ghsa-testing",
            ghsa_id="GHSA-f3x5-4pp6-r2mf",
            comment_body="   \n\t  ",
        )
