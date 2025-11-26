"""Common configuration for the PSRT GHSA Bot."""

import os
from typing import Final, Literal

DONT_COMMENT: bool = os.getenv("DONT_COMMENT", "").lower() in ("true", "1", "yes")

type CheckinStatus = Literal["in_progress", "ok", "error"]

MONITOR_SLUG_HEALTH: Final[str] = "psrt-health-monitor"
MONITOR_SLUG_GHSA: Final[str] = "psrt-ghsa-cron"
MONITOR_SLUG_PLAYWRIGHT: Final[str] = "psrt-playwright-cron"

STATUS_IN_PROGRESS: Final[CheckinStatus] = "in_progress"
STATUS_OK: Final[CheckinStatus] = "ok"
STATUS_ERROR: Final[CheckinStatus] = "error"
