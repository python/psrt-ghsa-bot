"""GitHub client utilities."""

import base64

from githubkit import AppAuthStrategy, GitHub

from psrt_ghsa_bot.settings import settings


def get_github_client() -> GitHub:
    """Create GitHub client authenticated as the GitHub App."""
    private_key = base64.b64decode(settings.github.GH_CLIENT_PRIVATE_KEY).decode().strip()
    return GitHub(AppAuthStrategy(settings.github.GH_CLIENT_ID, private_key))
