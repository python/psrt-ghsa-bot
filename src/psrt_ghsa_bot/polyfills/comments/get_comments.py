"""GitHub API polyfill for reading GHSA comments using Playwright.

GitHub does not provide REST/GraphQL API endpoints for reading comments
on Security Advisories in draft/triage state. This module uses browser
automation to extract comment data from the GitHub web UI.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from playwright.sync_api import Locator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient

logger = logging.getLogger(__name__)


@dataclass
class GHSAComment:
    """Represents a comment on a GitHub Security Advisory."""

    id: str
    """Unique identifier for the comment (extracted from DOM)"""
    author: str
    """GitHub username of the comment author"""
    body: str
    """Comment content/text"""
    created_at: datetime
    """Timestamp when comment was created"""
    updated_at: datetime
    """Timestamp when comment was last updated"""
    is_bot_comment: bool
    """True if comment is from <bot-username> or other bot account"""

    def __repr__(self) -> str:
        """For debugging."""
        return f"GHSAComment(id={self.id}, author={self.author}, created={self.created_at})"


def get_ghsa_comments(
    client: GitHubPlaywrightClient,
    owner: str,
    repo: str,
    ghsa_id: str,
) -> list[GHSAComment]:
    """Get all comments from a GitHub Security Advisory using Playwright.

    This function navigates to the GHSA page, extracts all comments from the
    timeline, and handles pagination if needed.

    Args:
        client: Authenticated GitHubPlaywrightClient instance
        owner: Repository owner (organization or user)
        repo: Repository name
        ghsa_id: GHSA identifier (e.g., GHSA-xxxx-xxxx-xxxx)

    Returns:
        List of GHSAComment objects in chronological order

    Raises:
        RuntimeError: If GHSA page cannot be loaded or comments cannot be parsed
        PlaywrightTimeoutError: If page load times out

    Example:
        >>> with GitHubPlaywrightClient() as client:
        ...     client.authenticate()
        ...     comments = get_ghsa_comments(client, "python", "cpython", "GHSA-1234-5678-9abc")
        ...     for comment in comments:
        ...         print(f"{comment.author}: {comment.body[:50]}")
    """
    client.navigate_to_ghsa(owner, repo, ghsa_id)

    if "404" in client.page.title() or client.page.locator("text=404").count() > 0:
        msg = f"Advisory {ghsa_id} not found or bot lacks access (collaborator permissions required)"
        raise PermissionError(msg)

    try:
        client.page.wait_for_selector(".timeline-comment, .js-comment", timeout=10000, state="attached")
    except PlaywrightTimeoutError:
        logger.debug("Timeout waiting for comments to load on %s", ghsa_id)

    _load_all_comments(client)
    return _extract_comments(client)


def _load_all_comments(client: GitHubPlaywrightClient) -> None:
    """Load all comments by clicking 'Load more' buttons until exhausted.

    GitHub may paginate comments with "Show more..." / "Load more" buttons.
    This function clicks them until all comments are visible.

    Args:
        client: GitHubPlaywrightClient instance
    """
    max_iterations = 50  # no loops allowee
    iteration = 0

    while iteration < max_iterations:
        load_more_selectors = [
            "button:has-text('Show more')",
            "button:has-text('Load more')",
            "a:has-text('Show more')",
            ".ajax-pagination-btn",
        ]

        load_more_button = None
        for selector in load_more_selectors:
            try:
                button = client.page.locator(selector).first
                if button.is_visible(timeout=1000):
                    load_more_button = button
                    break
            except PlaywrightTimeoutError:
                continue

        if not load_more_button:
            break

        try:
            load_more_button.click()
            client.page.wait_for_timeout(1000)
            iteration += 1
        except Exception:
            break


def _extract_comments(client: GitHubPlaywrightClient) -> list[GHSAComment]:
    """Extract all comment data from the current page.

    Uses multiple fallback selectors to handle GitHub UI changes.

    Args:
        client: GitHubPlaywrightClient instance

    Returns:
        List of parsed GHSAComment objects
    """
    comments: list[GHSAComment] = []
    comment_selectors = [
        ".js-comment-container .timeline-comment",
        ".timeline-comment",
        ".js-comment",
        "div.TimelineItem.js-comment-container",
    ]

    comment_elements: list[Locator] = []
    for selector in comment_selectors:
        try:
            elements = client.page.locator(selector).all()
            logger.debug("Selector '%s' found %d elements", selector, len(elements))
            if elements:
                comment_elements = elements
                break
        except Exception as e:
            logger.debug("Selector '%s' failed: %s", selector, e)
            continue

    if not comment_elements:
        logger.debug("No comment elements found with any selector")
        return comments

    logger.debug("Parsing %d comment elements", len(comment_elements))

    for idx, element in enumerate(comment_elements):
        try:
            comment = _parse_comment_element(element, idx)
            if comment:
                comments.append(comment)
                logger.debug("Parsed comment from @%s: %s", comment.author, comment.body[:30])
            else:
                logger.debug("Element %d returned None (not a comment)", idx)
        except Exception as e:
            logger.debug("Failed to parse element %d: %s", idx, e)
            continue

    return comments


# noinspection D
def _parse_comment_element(element: Locator, fallback_idx: int) -> GHSAComment | None:
    """Parse a single comment element into a GHSAComment object.

    Args:
        element: Playwright locator for the comment container
        fallback_idx: Index to use if comment ID cannot be extracted

    Returns:
        Parsed GHSAComment or None if parsing fails
    """
    comment_id = None
    for attr in ["data-comment-id", "id", "data-gid"]:
        try:
            comment_id = element.get_attribute(attr)
            if comment_id:
                break
        except Exception:
            logger.exception("Failed to get attribute %s", attr)
            continue

    if not comment_id:
        comment_id = f"comment-{fallback_idx}"

    author = None
    author_selectors = [
        ".author",
        ".timeline-comment-header .author",
        "[data-hovercard-type='user']",
        ".comment-user",
        "a.Link--primary",
    ]

    for selector in author_selectors:
        try:
            author_element = element.locator(selector).first
            author = author_element.text_content(timeout=1000)
            if author:
                author = author.strip()
                break
        except Exception:
            logger.exception("Failed to get author with selector %s", selector)
            continue

    if not author:
        logger.debug("Element %d: No author found, skipping", fallback_idx)
        return None

    body = None
    body_selectors = [
        ".comment-body",
        ".markdown-body",
        "[data-testid='comment-body']",
        ".js-comment-body",
    ]

    for selector in body_selectors:
        try:
            body_element = element.locator(selector).first
            body = body_element.text_content(timeout=1000)
            if body:
                body = body.strip()
                break
        except Exception:
            logger.exception("Failed to get body with selector %s", selector)
            continue

    if not body:
        body = ""  # empty? comment body

    created_at = _extract_timestamp(element, "created")
    updated_at = _extract_timestamp(element, "updated") or created_at

    is_bot = _is_bot_author(element, author)

    return GHSAComment(
        id=comment_id,
        author=author,
        body=body,
        created_at=created_at,
        updated_at=updated_at,
        is_bot_comment=is_bot,
    )


def _extract_timestamp(element: Locator, timestamp_type: str) -> datetime:
    """Extract created or updated timestamp from comment element.

    Args:
        element: Comment element locator
        timestamp_type: "created" or "updated"

    Returns:
        Parsed datetime or current time as fallback
    """
    timestamp_selectors = [
        "relative-time",
        "time[datetime]",
        ".timestamp",
        f"[title*='{timestamp_type}']",
    ]

    for selector in timestamp_selectors:
        try:
            time_element = element.locator(selector).first
            datetime_str = time_element.get_attribute("datetime", timeout=1000)
            if datetime_str:
                return datetime.fromisoformat(datetime_str)
        except Exception:
            logger.exception("Failed to get timestamp with selector %s", selector)
            continue

    return datetime.now(tz=UTC)


def _is_bot_author(element: Locator, author: str) -> bool:
    """Determine if comment author is a bot account.

    Args:
        element: Comment element locator
        author: Author username

    Returns:
        True if author is a bot
    """
    if "bot" in author.lower():
        return True

    try:
        bot_badge = element.locator(".Label:has-text('Bot')").first
        return bot_badge.is_visible(timeout=500)
    except Exception:
        return False
