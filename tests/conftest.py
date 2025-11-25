"""Shared pytest config & fixtures."""

from pathlib import Path

import pytest

PLAYWRIGHT_FULL = Path("tests/PLAYWRIGHT_FULL.test").exists()
AUTH_STATE_EXISTS = Path("playwright/.auth/github_state.json").exists()

requires_playwright_auth = pytest.mark.skipif(
    not (PLAYWRIGHT_FULL and AUTH_STATE_EXISTS),
    reason="Requires PLAYWRIGHT_FULL.test file and authentication state",
)
