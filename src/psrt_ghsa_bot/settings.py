"""Bot configuration settings."""

import os
from dataclasses import MISSING, dataclass, fields
from pathlib import Path
from typing import Final, Literal, Self, TypeVar

from dotenv import load_dotenv

BASE_DIR: Final[Path] = Path(__file__).parent.parent

load_dotenv()

T = TypeVar("T")


def _load_from_env[T](cls: type[T]) -> T:
    """Helper to load dataclass fields from environment variables."""
    kwargs = {}

    for field in fields(cls):
        env_var = field.name
        env_value = os.getenv(env_var)

        if env_value is not None:
            if field.type is int:
                kwargs[field.name] = int(env_value)
            elif field.type is Path:
                kwargs[field.name] = Path(env_value)
            else:
                kwargs[field.name] = env_value
        elif field.default is not MISSING:
            kwargs[field.name] = field.default
        elif field.default_factory is not MISSING:
            kwargs[field.name] = field.default_factory()

    return cls(**kwargs)


@dataclass
class GitHubAppSettings:
    """GitHub App API settings."""

    GH_CLIENT_ID: str
    """GitHub App Installation Client ID."""
    GH_CLIENT_PRIVATE_KEY: str
    """GitHub App Installation Private Key."""

    @classmethod
    def from_env(cls) -> Self:
        """Load from environment variables."""
        return _load_from_env(cls)


@dataclass
class CVESettings:
    """CVE API settings."""

    CVE_USERNAME: str
    """CVE API username."""
    CVE_API_KEY: str
    """CVE API key."""
    CVE_ENV: Literal["dev", "test", "prod"] = "test"
    """CVE API environment."""

    @classmethod
    def from_env(cls) -> Self:
        """Load from environment variables."""
        return _load_from_env(cls)


@dataclass
class PlaywrightSettings:
    """Playwright browser automation settings."""

    GH_BOT_PASSWORD: str
    """GitHub password for the bot."""
    GH_BOT_OTP_SECRET: str
    """GitHub TOTP/2FA secret for the bot."""
    GH_BOT_USERNAME: str = "PSRT-GHSA-Automation"
    """GitHub username for the bot."""
    GH_AUTH_STATE_PATH: Path = Path(f"{BASE_DIR}/playwright/.auth/github_state.json")
    """Path to Playwright auth state file."""

    @classmethod
    def from_env(cls) -> Self:
        """Load from environment variables."""
        return _load_from_env(cls)


@dataclass
class ReminderSettings:
    """Reminder and deadline settings."""

    DEFAULT_NOTIFICATION_TEAM: str = "python/psrt"
    """Team to notify when a GHSA is created."""
    DEFAULT_DEADLINE_DAYS: int = 90
    """Days until deadline from creation date."""
    DEFAULT_WARNING_THRESHOLD_DAYS: int = 14
    """Days before deadline to send warning."""
    HOURS_BETWEEN_REMINDERS: int = 23
    """Minimum hours between daily reminders."""
    URGENT_DAYS_THRESHOLD: int = 7
    """Days threshold for urgent warnings."""

    @classmethod
    def from_env(cls) -> Self:
        """Load from environment variables."""
        return _load_from_env(cls)


@dataclass
class MonitoringSettings:
    """Monitoring and error tracking settings."""

    SENTRY_DSN: str | None = None
    """Sentry DSN for error tracking."""

    @classmethod
    def from_env(cls) -> Self:
        """Load from environment variables."""
        return _load_from_env(cls)


@dataclass
class Settings:
    """Combined application settings so we can import `from .settings import settings` below."""

    github: GitHubAppSettings
    cve: CVESettings
    playwright: PlaywrightSettings
    reminders: ReminderSettings
    monitoring: MonitoringSettings

    @classmethod
    def from_env(cls) -> Self:
        """Load all settings from environment variables."""
        return cls(
            github=GitHubAppSettings.from_env(),
            cve=CVESettings.from_env(),
            playwright=PlaywrightSettings.from_env(),
            reminders=ReminderSettings.from_env(),
            monitoring=MonitoringSettings.from_env(),
        )


settings = Settings.from_env()
