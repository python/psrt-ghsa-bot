# PSRT GHSA Bot

Bot which adds the PSRT GitHub team (`python/psrt`) and CVE IDs to GitHub Security Advisories.

## Moving Pieces

### GitHub Actions

- The cron bot runs off of [`.github/workflows/cron.yml`](.github/workflows/cron.yml) and runs at the top of each hour.
  - Calls [src/psrt_ghsa_bot/app.py](src/psrt_ghsa_bot/app.py)
  - Fetches open GHSAs from all installed orgs/repos
  - Adds PSRT team to GHSAs without it
  - Assigns CVE IDs to draft GHSAs without one
- The Playwright bot runs off of [`.github/workflows/playwright.yml`](.github/workflows/playwright.yml) and runs every 5 minutes.
  - Calls [src/psrt_ghsa_bot/comment_processor.py](src/psrt_ghsa_bot/comment_processor.py)
  - Reads GHSA comments via Playwright (no API available)
  - Parses `@<bot-username>` commands, executes if authorized
  - Posts responses, tracks state in `state.json`
- Health checks are done via [`.github/workflows/health-check.yml`](.github/workflows/health-check.yml) and runs every 15 minutes.
  - It checks the status using the `gh` CLI and reports to Sentry if the bot is not healthy via Sentry cron monitors.

### Why Playwright?

The GHSA API is limited and has not really been developed in awhile. As such, it is missing a lot of features
like:
- Commenting on GHSAs
- Adding teams to GHSAs
- Assigning CVE IDs to GHSAs
- Removing temporary forks generated inside a GHSA that collaboraters use fro remediation
- No webhooks to respond to things.. so we do the GHA polling thing...

That's why there is this weird split between the cron.yml and playwright.yml. As API things
are added, we can move more into app.py/cron.yml and remove the playwright stuff (gladly!)

## Development

Uses `uv` for dependency management and `pytest` for testing.

### Setup

Make sure you have `uv` installed athttps://docs.astral.sh/uv/getting-started/installation/
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
- Take your org 