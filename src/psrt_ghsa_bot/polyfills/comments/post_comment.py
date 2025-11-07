"""For posting comments to GHSA using Playwright."""

from typing import TYPE_CHECKING

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient


def post_ghsa_comment(
    client: GitHubPlaywrightClient,
    owner: str,
    repo: str,
    ghsa_id: str,
    comment_body: str,
) -> str:
    """Post a comment to a GitHub Security Advisory using Playwright.

     Navigates to the GHSA page, locates the comment form,
    fills in the comment text, and submits it.

    Args:
        client: Authenticated GitHubPlaywrightClient instance
        owner: Repository owner (organization or user)
        repo: Repository name
        ghsa_id: GHSA identifier (e.g., GHSA-xxxx-xxxx-xxxx)
        comment_body: The text content of the comment to post

    Returns:
        Comment ID of the newly created comment

    Raises:
        RuntimeError: If comment cannot be posted or form not found
        PlaywrightTimeoutError: If page load or form submission times out
        ValueError: If comment_body is empty

    Example:i
        >>> with GitHubPlaywrightClient() as client:
        ...     client.authenticate()
        ...     comment_id = post_ghsa_comment(
        ...         client,
        ...         "python",
        ...         "cpython",
        ...         "GHSA-1234-5678-9abc",
        ...         "This vulnerability has been verified."
        ...     )
        ...     print(f"Posted comment: {comment_id}")
    """
    if not comment_body or not comment_body.strip():
        raise ValueError("comment_body cannot be empty")

    client.navigate_to_ghsa(owner, repo, ghsa_id)

    _fill_comment_form(client, comment_body)
    _submit_comment(client)

    comment_id = _wait_for_comment_posted(client, comment_body)
    return comment_id


def _fill_comment_form(client: GitHubPlaywrightClient, comment_body: str) -> None:
    """Locate and fill the comment textarea.

    Args:
        client: GitHubPlaywrightClient instance
        comment_body: Comment text to fill in

    Raises:
        RuntimeError: If comment form cannot be found
    """
    try:
        textarea = client.page.locator('textarea[name="body"]').first
        textarea.wait_for(state="visible", timeout=10000)
        textarea.click()
        textarea.fill(comment_body)
    except PlaywrightTimeoutError:
        raise RuntimeError(
            "Could not find comment textarea. The page structure may have changed, "
            "or you may not have permission to comment on this advisory."
        )


def _submit_comment(client: GitHubPlaywrightClient) -> None:
    """Submit the comment form.

    Args:
        client: GitHubPlaywrightClient instance

    Raises:
        RuntimeError: If submit button cannot be found or clicked
    """
    try:
        submit_button = client.page.locator('button[type="submit"][name="comment"]').first
        submit_button.wait_for(state="visible", timeout=5000)
        submit_button.click()
    except PlaywrightTimeoutError:
        raise RuntimeError("Could not find comment submit button. The page structure may have changed.")


def _wait_for_comment_posted(
    client: GitHubPlaywrightClient,
    expected_body: str,
    timeout: int = 15000,
) -> str:
    """Wait for the comment to appear on the page after submission.

    Args:
        client: GitHubPlaywrightClient instance
        expected_body: The comment body we expect to see
        timeout: Maximum time to wait in milliseconds

    Returns:
        The ID of the newly posted comment

    Raises:
        RuntimeError: If comment doesn't appear within timeout
    """
    client.page.wait_for_timeout(2000)

    try:
        # Find timeline item containing our comment text by checking text content
        timeline_items = client.page.locator(".TimelineItem").all()

        for item in timeline_items:
            try:
                text_content = item.text_content(timeout=1000)
                if text_content and expected_body.strip() in text_content:
                    comment_id = item.get_attribute("id")
                    if comment_id and comment_id.startswith("advisory-comment-"):
                        return comment_id.replace("advisory-comment-", "")
                    return "comment-posted"
            except Exception:
                continue

        raise RuntimeError(
            f"Comment was submitted but could not be found on the page within {timeout}ms. "
            "It may have been posted successfully but not yet visible."
        )

    except PlaywrightTimeoutError:
        raise RuntimeError(
            f"Comment was submitted but could not be found on the page within {timeout}ms. "
            "It may have been posted successfully but not yet visible."
        )
