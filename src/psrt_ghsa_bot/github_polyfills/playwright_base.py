"""Base Playwright client for GitHub UI automation.

This module provides authentication and navigation utilities for automating
GitHub web UI interactions that are not available through the API.
"""

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

load_dotenv()


class GitHubPlaywrightClient:
    """Client for automating GitHub UI interactions using Playwright.

    Contains helpers to quickly login, go to GHSA, and interact with the UI.
    Also some debug options for localdev like slow_mo and record_video
    and headless/nonheadless so you can see whats happening if something break
    """

    def __init__(
        self,
        headless: bool = True,
        auth_token: str | None = None,
        storage_state_path: str | None = None,
        slow_mo: int = 0,
        record_video: bool = False,
    ) -> None:
        """Initialize the GitHub Playwright client.

        Args:
            headless: Whether to run browser in headless mode
            auth_token: GitHub personal access token for authentication
            storage_state_path: Path to saved authentication state file
            slow_mo: Slow down operations by specified milliseconds (useful for debugging)
            record_video: Whether to record videos of browser sessions
        """
        self.headless = headless
        self.auth_token = auth_token or os.getenv("GH_AUTH_TOKEN")
        self.storage_state_path = storage_state_path or os.getenv(
            "GH_AUTH_STATE_PATH",
            "playwright/.auth/github_state.json",
        )
        self.slow_mo = slow_mo
        self.record_video = record_video

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "GitHubPlaywrightClient":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def start(self) -> None:
        """Start the Playwright browser session."""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
        )

        storage_state_file = Path(self.storage_state_path)
        storage_state: str | None = None
        if storage_state_file.exists():
            storage_state = str(storage_state_file)

        context_options: dict[str, Any] = {"storage_state": storage_state}
        if self.record_video:
            context_options["record_video_dir"] = "playwright-videos/"

        self._context = self._browser.new_context(**context_options)
        self._page = self._context.new_page()

    def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self._page:
            self._page.close()
            self._page = None
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    @property
    def page(self) -> Page:
        """Get the current page instance."""
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first or use context manager.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        """Get the current browser context."""
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first or use context manager.")
        return self._context

    def authenticate(self, force: bool = False) -> None:
        """Authenticate to GitHub using storage state or credentials.

        Authentication methods tried in order:
        1. Existing storage state (saved session) - PREFERRED
        2. Automated login with GH_BOT_USERNAME/GH_BOT_PASSWORD

        # if user/pass/otp is not sufficient the only other options
        # i think we could do is oauth maybe? GH_SESSION storing
        # requires rotating it manually every 30 days or so...
        # this was easiestf or now!

        Args:
            force: Force re-authentication even if state exists

        Raises:
            RuntimeError: If all authentication methods fail
        """
        storage_state_file = Path(self.storage_state_path)

        # Check if we already have a valid session loaded from storage state
        # else we need to login (below)
        if storage_state_file.exists() and not force:
            print("🔍 Checking saved authentication state...")
            if self._is_authenticated():
                print("✅ Using saved authentication state")
                return
            else:
                print("⚠️  Saved state is invalid or expired, re-authenticating...")

        username = os.getenv("GH_BOT_USERNAME")
        password = os.getenv("GH_BOT_PASSWORD")
        if username and password:
            print(f"🔐 Logging in as {username}...")
            self._login_with_credentials(username, password)
            # Save the new session state
            storage_state_file.parent.mkdir(parents=True, exist_ok=True)
            self.context.storage_state(path=str(storage_state_file))
            print("✅ Login successful, state saved")
            return

        raise RuntimeError(
            "Authentication failed. Set GH_BOT_USERNAME and GH_BOT_PASSWORD environment variables, "
            "or use authenticate_manual() for interactive login."
        )

    def authenticate_manual(self, timeout: int = 300_000) -> None:
        """Perform manual authentication via GitHub's login page.

        This method navigates to GitHub's login page and waits for the user
        to complete the login process manually. Once authenticated, the session
        state is saved for future use.

        Args:
            timeout: Maximum time to wait for manual login (in milliseconds)
        """
        self.page.goto("https://github.com/login")

        print("\n" + "=" * 60)
        print("MANUAL AUTHENTICATION REQUIRED")
        print("=" * 60)
        print("\nPlease log in to GitHub in the browser window.")
        print("The session will be saved for future automated runs.")
        print(f"\nWaiting up to {timeout / 1000} seconds...")
        print("=" * 60 + "\n")

        # Wait for successful login by checking for redirect to main page
        # or presence of user menu
        try:
            self.page.wait_for_url("https://github.com/**", timeout=timeout)
            self.page.wait_for_selector("button[aria-label='Open user navigation menu']", timeout=10000)
        except Exception as e:
            raise RuntimeError(f"Manual authentication failed or timed out: {e}")

        storage_state_file = Path(self.storage_state_path)
        storage_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(storage_state_file))

        print("\n✅ Authentication successful! Session saved.")
        print(f"   State saved to: {storage_state_file}\n")

    def _login_with_credentials(self, username: str, password: str) -> None:
        """Perform automated login with username and password.

        This handles the standard GitHub login flow. 2FA must be pre-approved
        or the storage state from setup_auth.py must be used.

        Args:
            username: GitHub username
            password: GitHub password

        Raises:
            RuntimeError: If login fails or requires 2FA
        """
        self.page.goto("https://github.com/login", wait_until="networkidle", timeout=30000)
        self.page.wait_for_selector('input[name="login"]', state="visible", timeout=15000)

        self.page.locator('input[name="login"]').fill(username)
        self.page.locator('input[name="password"]').fill(password)
        self.page.locator('input[type="submit"][value="Sign in"]').click()

        self.page.wait_for_timeout(2000)

        if "sessions/two-factor" in self.page.url:
            otp_secret = os.getenv("GH_BOT_OTP_SECRET")
            if not otp_secret:
                raise RuntimeError(
                    "2FA required but GH_BOT_OTP_SECRET not set. "
                    "Set environment variable or use authenticate_manual() for interactive login."
                )

            try:
                import pyotp

                totp = pyotp.TOTP(otp_secret)
                otp_code = totp.now()
                print("   Using OTP code for 2FA...")

                self.page.locator('input[name="app_otp"]').fill(otp_code)
                self.page.locator('button[type="submit"]:has-text("Verify")').click()
                self.page.wait_for_timeout(3000)

            except ImportError:
                raise RuntimeError("2FA required but pyotp not installed. did you 'uv sync' the project?")

        if not self._is_authenticated():
            raise RuntimeError("Login failed - authentication check failed")

    def _is_authenticated(self) -> bool:
        """Check if the current session is authenticated.

        Checks cookies for dotcom_user or user_session indicators.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            self.page.goto("https://github.com", wait_until="domcontentloaded", timeout=15000)

            cookies = self.context.cookies()
            auth_cookies = {
                cookie["name"]: cookie for cookie in cookies if cookie["domain"] in [".github.com", "github.com"]
            }

            has_user_session = "user_session" in auth_cookies
            has_dotcom_user = "dotcom_user" in auth_cookies

            return has_user_session and has_dotcom_user
        except Exception as e:
            print(f"   Debug: Auth check failed - {e}")
            return False

    def navigate_to_ghsa(self, owner: str, repo: str, ghsa_id: str) -> None:
        """Navigate to a specific GitHub Security Advisory page.

        Does some fanangling because networkidle never happens since
        GH does polling for live updates to broadcas to everyone
        subscribed to the ws.

        Args:
            owner: Repository owner (organization or user)
            repo: Repository name
            ghsa_id: GHSA identifier (e.g., GHSA-xxxx-xxxx-xxxx)
        """
        url = f"https://github.com/{owner}/{repo}/security/advisories/{ghsa_id}"
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)

        try:
            self.page.wait_for_selector(".js-timeline-item, .TimelineItem", timeout=15000)
        except Exception:
            self.page.wait_for_selector("body", timeout=5000)

    def wait_for_page_ready(self, timeout: int = 30000) -> None:
        """Wait for the page to be fully loaded and interactive.

        Uses domcontentloaded instead of networkidle because GitHub pages
        maintain WebSocket connections for live updates which prevent
        networkidle from ever being reached.

        Args:
            timeout: Maximum time to wait in milliseconds
        """
        self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
