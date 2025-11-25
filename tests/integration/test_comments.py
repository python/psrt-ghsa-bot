"""Integration tests for GHSA comment functionality (hit live GitHub)."""

from datetime import datetime

import pytest
from tests.integration.conftest import requires_playwright_auth

from psrt_ghsa_bot.polyfills import (
    GitHubPlaywrightClient,
    get_ghsa_comments,
    post_ghsa_comment,
)


@requires_playwright_auth
def test_get_ghsa_comments_basic(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test basic comment retrieval from a GHSA."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )
    assert isinstance(comments, list)


@requires_playwright_auth
def test_get_ghsa_comments_with_no_comments(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test retrieval from a GHSA with no comments."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )
    assert isinstance(comments, list)


@requires_playwright_auth
def test_get_ghsa_comments_bot_detection(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test that bot comments are properly detected."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    bot_comments = [c for c in comments if c.is_bot_comment]
    for bot_comment in bot_comments:
        assert "bot" in bot_comment.author.lower() or "[bot]" in bot_comment.author


@requires_playwright_auth
def test_get_ghsa_comments_chronological_order(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test that comments are returned in chronological order."""
    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    if len(comments) >= 2:
        for i in range(len(comments) - 1):
            assert comments[i].created_at <= comments[i + 1].created_at


@requires_playwright_auth
def test_get_ghsa_comments_error_handling_invalid_ghsa() -> None:
    """Test error handling for invalid GHSA ID."""
    with GitHubPlaywrightClient(headless=True) as client:
        client.authenticate()

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


@requires_playwright_auth
def test_get_ghsa_comments_pagination() -> None:
    """Test pagination handling for GHSAs with many comments."""
    with GitHubPlaywrightClient(headless=True) as client:
        client.authenticate()

        comments = get_ghsa_comments(
            client,
            owner="test-org",
            repo="test-repo",
            ghsa_id="GHSA-xxxx-xxxx-xxxx",
        )

        assert len(comments) > 20


@requires_playwright_auth
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


@requires_playwright_auth
def test_post_and_read_comment_roundtrip(authenticated_client: GitHubPlaywrightClient) -> None:
    """Test posting a comment and then reading it back."""
    unique_text = f"Roundtrip test {datetime.now().timestamp()}"

    comment_id = post_ghsa_comment(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
        comment_body=unique_text,
    )

    assert comment_id is not None

    comments = get_ghsa_comments(
        authenticated_client,
        owner="jolt-org",
        repo="ghsa-testing",
        ghsa_id="GHSA-f3x5-4pp6-r2mf",
    )

    posted_comment = next((c for c in comments if unique_text in c.body), None)
    assert posted_comment is not None
    assert posted_comment.body == unique_text


@requires_playwright_auth
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
