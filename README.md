# PSRT GHSA Bot

Bot which adds the PSRT GitHub team (`python/psrt`) and CVE IDs to GitHub Security Advisories.

## Architecture

### GitHub Actions

- The cron bot runs off of [`.github/workflows/cron.yml`](.github/workflows/cron.yml) and runs at the top of each hour.
  - Calls [src/psrt_ghsa_bot/api_app.py](src/psrt_ghsa_bot/api_app.py)
  - Fetches open GHSAs from all installed orgs/repos
  - Adds PSRT team to GHSAs without it
  - Assigns CVE IDs to draft GHSAs without one
- The Playwright bot runs off of [`.github/workflows/playwright.yml`](.github/workflows/playwright.yml) and runs every 5 minutes.
  - Calls [src/psrt_ghsa_bot/comment_processor.py](src/psrt_ghsa_bot/comment_processor.py)
  - Reads GHSA comments via Playwright (no API available)
  - Parses `@<bot-username>` commands, executes if authorized
  - Posts responses, tracks state in `state.json`
- Health checks are done via [`.github/workflows/health-check.yml`](.github/workflows/health-check.yml) and runs every 15 minutes.
  - It checks workflow run status via the GitHub API and reports to Sentry cron monitors if unhealthy.

### Why Playwright?

The GHSA API is limited and has not really been developed in awhile. As such, it is missing a lot of features
like:
- Commenting on GHSAs
- Adding teams to GHSAs
- Assigning CVE IDs to GHSAs
- Removing temporary forks generated inside a GHSA that collaborators use fro remediation
- No webhooks to respond to things.. so we do the GHA polling thing...

That's why there is this weird split between the cron.yml and playwright.yml. As API things
are added, we can move more into api_app.py/cron.yml and remove the playwright stuff (gladly!)

## Installation

The GitHub app (API-related activities) **MUST** be installed in all GitHub organizations
you want scanned. The GitHub user (`GH_BOT_USERNAME`, used by Playwright) **MUST** have access to the repos that
you want to interact with.

**Important:** The GitHub App installation and GitHub user require the same permissions on repositories.
The Playwright bot uses the GitHub App installation to generate a list of repos
(~[comment_processor.py:130-140](src/psrt_ghsa_bot/comment_processor.py#L130-L140)), so any permission
mismatch will cause failures

### GitHub App Permissions

The GitHub App requires the following permissions:

| Permission        | Access       | Purpose                                               |
|-------------------|--------------|-------------------------------------------------------|
| `security_events` | Read & Write | Access and update security advisories, assign CVE IDs |
| `actions`         | Read         | Health check monitoring of workflow runs              |
| `members`         | Read         | Verify team membership for command authorization      |
| `metadata`        | Read         | Required for basic repository access                  |

### Playwright Bot User Requirements

The bot user (`GH_BOT_USERNAME`) requires:

- **Organization membership** in all orgs where the GitHub App is installed
- **Repository access** matching the GitHub App installation scope
- **2FA enabled** with TOTP (the bot uses `GH_BOT_OTP_SECRET` for authentication)
- **Write access** to security advisories (to post comments via browser automation)

## Development

Uses `uv` for dependency management and `pytest` for testing.

### Setup

Make sure you have `uv` installed at https://docs.astral.sh/uv/getting-started/installation/
Quickly, for Linux/macOS:
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```
or (not recommended):
```shell
pipx install uv
```

Afterwards, you can use `make` to run the commands in the [`Makefile`](Makefile).
- `make upgrade` - Upgrade all dependencies to the latest stable versions.

Every time you run `uv run` or anything it automatically installs/syncs the dependencies
and it's near-instant so there is no `make install` or anything.

### Tests

Only unique things here are `PLAYWRIGHT_FULL.test`, which can can see more about in [`PLAYWRIGHT_FULL.test.example`](tests/PLAYWRIGHT_FULL.test.example). 
This just tells the [`Makefile`](Makefile) target `make test` to run `playwright install` before running the tests
and then enables some of the skipped tests. These tests assume a test organization and all the setup behind that
because it is an integration test and will comment on and read a GHSA advisory.

### Scripts

There is a [`scripts/`](scripts/) directory with some local dev scripts, namely one that will
set up an organization with all the things needed to develop (TODO: it doesn't actually do anything yet.)

The idea behind the bootstrap_org.py is that it will:
- Take your test org, set up a `psrt` (or whatever) team, create a repo with some GHSA, then comment, read the comments, etc.
This helps more from the integration testing side of things without doing it all in some public, busy repo like `python/CPython` :)