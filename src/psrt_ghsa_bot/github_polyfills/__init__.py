"""GitHub API polyfills using Playwright for UI automation.

Things that we can't do with the GitHub API but need to do with Playwright
like commnet reading (commands like '@psrt-bot do the thing'), etc.
"""

from .playwright_base import GitHubPlaywrightClient

__all__ = ["GitHubPlaywrightClient"]
