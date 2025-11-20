"""Helpers to be used by the bot when needed."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient

logger = logging.getLogger(__name__)


def take_debug_screenshot(client: GitHubPlaywrightClient, ghsa_id: str) -> None:
    """Take a screenshot, saving locally to disk.

    Args:
        client: Playwright client
        ghsa_id: GHSA ID for the advisory
    """
    logger.debug("Taking debug screenshot for %s", ghsa_id)
    client.page.screenshot(path=f"debug_{ghsa_id}.png")
    logger.info("Screenshot saved to debug_%s.png", ghsa_id)
