"""GitHub API polyfills using Playwright for UI automation.

Things that we can't do with the GitHub API but need to do with Playwright
like comment reading/writing, etc.
"""

from psrt_ghsa_bot.polyfills.comments import GHSAComment, get_ghsa_comments, post_ghsa_comment
from psrt_ghsa_bot.polyfills.playwright_base import GitHubPlaywrightClient

__all__ = ["GitHubPlaywrightClient", "GHSAComment", "get_ghsa_comments", "post_ghsa_comment"]
