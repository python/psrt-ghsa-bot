"""Tests for GHSA comment functionality (reading and writing)."""

import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from githubkit import GitHub, TokenAuthStrategy

from psrt_ghsa_bot.polyfills import (
    GHSAComment,
    GitHubPlaywrightClient,
    get_ghsa_comments,
    post_ghsa_comment,
)

if TYPE_CHECKING:
    from collections.abc import Generator

PLAYWRIGHT_FULL = Path("tests/PLAYWRIGHT_FULL.test").exists()


@pytest.fixture
def authenticated_client() -> Generator[GitHubPlaywrightClient]:
    """Create an authenticated GitHubPlaywrightClient instance for testing."""
    client = GitHubPlaywrightClient(headless=True)
    client.start()
    client.authenticate()
    yield client
    client.close()


@pytest.fixture
def test_ghsa() -> Generator[dict[str, str]]:
    """Create a test GHSA and clean it up after the test.

    Returns dict with: owner, repo, ghsa_id
    """
    token = os.getenv("GH_AUTH_TOKEN")
    if not token:
        pytest.skip("GH_AUTH_TOKEN not set")

    github = GitHub(TokenAuthStrategy(token))  # type: ignore[arg-type]
    owner = "jolt-org"
    repo = "ghsa-testing"

    # Create a test advisory
    response = github.rest.security_advisories.create_repository_advisory(
        owner=owner,
        repo=repo,
        data={
            "summary": f"Test Advisory {datetime.now().timestamp()}",
            "description": "This is a test advisory created by pytest. It will be deleted automatically.",
            "severity": "low",
            "vulnerabilities": [
                {
                    "package": {"ecosystem": "pip", "name": "test-package"},
                    "vulnerable_version_range": "< 1.0.0",
                }
            ],
        },
    )

    ghsa_id = response.parsed_data.ghsa_id

    yield {"owner": owner, "repo": repo, "ghsa_id": ghsa_id}

    # Cleanup: Close/delete the advisory
    # Note: GitHub doesn't allow deleting advisories via API, but we can close them
    try:
        github.rest.security_advisories.update_repository_advisory(
            owner=owner,
            repo=repo,
            ghsa_id=ghsa_id,
            data={"state": "closed"},
        )
    except Exception:
        pass  # Best effort cleanup


@pytest.mark.skip(reason="idk how to test this actually")
def test_get_ghsa_comments_basic(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test basic comment retrieval from a GHSA."""
    # Use a test GHSA that we know has comments
    get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )
    #
    # # Verify we got a list (may be empty if no comments exist)
    # assert isinstance(comments, list)
    #
    # # If there are comments, verify their structure
    # for comment in comments:
    #     assert isinstance(comment, GHSAComment)
    #     assert isinstance(comment.id, str)
    #     assert isinstance(comment.author, str)
    #     assert isinstance(comment.body, str)
    #     assert isinstance(comment.created_at, datetime)
    #     assert isinstance(comment.updated_at, datetime)
    #     assert isinstance(comment.is_bot_comment, bool)
    #
    #     # Basic validation
    #     assert len(comment.id) > 0
    #     assert len(comment.author) > 0
    #     # Body can be empty
    #     assert comment.created_at <= datetime.now()
    #     assert comment.updated_at <= datetime.now()
    #     assert comment.created_at <= comment.updated_at


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
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


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
def test_get_ghsa_comments_with_no_comments(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test retrieval from a GHSA with no comments."""
    # Create or find a GHSA with zero comments
    # For now, we'll just verify the function handles empty comment lists
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",  # May or may not have comments
    )

    # Should return an empty list if no comments, not error
    assert isinstance(comments, list)


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
def test_get_ghsa_comments_bot_detection(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test that bot comments are properly detected."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    # Check if any bot comments are detected
    bot_comments = [c for c in comments if c.is_bot_comment]

    for bot_comment in bot_comments:
        assert "bot" in bot_comment.author.lower() or "[bot]" in bot_comment.author


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
def test_get_ghsa_comments_chronological_order(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test that comments are returned in chronological order."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    # If we have multiple comments, verify they're in chronological order
    if len(comments) >= 2:
        for i in range(len(comments) - 1):
            assert comments[i].created_at <= comments[i + 1].created_at


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


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
def test_get_ghsa_comments_error_handling_invalid_ghsa() -> None:
    """Test error handling for invalid GHSA ID."""
    with GitHubPlaywrightClient(headless=True) as client:
        client.authenticate()

        # Try to get comments from a non-existent GHSA
        # Should raise PermissionError for 404/access denied
        with pytest.raises((PermissionError, Exception)) as exc_info:
            get_ghsa_comments(
                client,
                owner="jolt-org",
                repo="ghsa-testing",
                ghsa_id="GHSA-0000-0000-0000",
            )

        if exc_info.type is not PermissionError:
            error_msg = str(exc_info.value).lower()
            assert "ghsa" in error_msg or "404" in error_msg or "not found" in error_msg


@pytest.mark.skip(reason="Integration test - requires specific test GHSA with known comment count")
def test_get_ghsa_comments_pagination() -> None:
    """Test pagination handling for GHSAs with many comments.

    This test should be run against a GHSA with enough comments to trigger
    pagination (typically >20 comments).
    """
    with GitHubPlaywrightClient(headless=True) as client:
        client.authenticate()

        # TODO: Create or find a test GHSA with >20 comments
        comments = get_ghsa_comments(
            client,
            owner="test-org",
            repo="test-repo",
            ghsa_id="GHSA-xxxx-xxxx-xxxx",
        )

        # Verify we got all comments, not just the first page
        assert len(comments) > 20


# ============================================================================
# POST COMMENT TESTS
# ============================================================================


@pytest.mark.skip(reason="Requires test GHSA creation (needs write permissions)")
def test_post_ghsa_comment_basic(authenticated_client: GitHubPlaywrightClient, test_ghsa: dict[str, str]) -> None:
    """Test basic comment posting to a GHSA."""
    test_comment = f"Test comment from pytest at {datetime.now().isoformat()}"

    comment_id = post_ghsa_comment(
        authenticated_client,
        owner=test_ghsa["owner"],
        repo=test_ghsa["repo"],
        ghsa_id=test_ghsa["ghsa_id"],
        comment_body=test_comment,
    )

    assert isinstance(comment_id, str)
    assert len(comment_id) > 0


@pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and Path("playwright/.auth/github_state.json").exists()),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
def test_post_and_read_comment_roundtrip(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test posting a comment and then reading it back."""
    unique_text = f"Roundtrip test {datetime.now().timestamp()}"

    # Post the comment
    comment_id = post_ghsa_comment(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
        comment_body=unique_text,
    )

    assert comment_id is not None

    # Read comments back
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    # Find our comment
    posted_comment = next((c for c in comments if unique_text in c.body), None)
    assert posted_comment is not None
    assert posted_comment.body == unique_text


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


@pytest.mark.skip(reason="Manual test - posts to real GHSA")
def test_post_comment_with_markdown(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test posting a comment with markdown formatting."""
    markdown_comment = f"""# Test Comment {datetime.now().timestamp()}

This comment contains **bold**, *italic*, and `code`.

- List item 1
- List item 2

```python
def hello():
    return "world"
```
"""

    comment_id = post_ghsa_comment(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
        comment_body=markdown_comment,
    )

    assert isinstance(comment_id, str)
    assert len(comment_id) > 0
