.DEFAULT_GOAL:=help
.ONESHELL:
ACT_INSTALLED := $(shell command -v act 2> /dev/null)

.PHONY: help upgrade lint fmt fmt-check type-check ty check test ci
.PHONY: act-check act-list act-ci act-health-check act-playwright act-cron
.PHONY: cron playwright health-check

help: ## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

upgrade: ## Upgrade all dependencies to the latest stable versions
	@uv lock --upgrade
	@echo "=> Dependencies Updated"

lint:  ## Lint the code
	@uv run ruff check --fix --unsafe-fixes .

fmt:  ## Format the code
	@uv run ruff format .

fmt-check:  ## Runs Ruff format in check mode (no changes)
	@uv run --no-sync ruff format --check .

type-check:  ## Run type-checking
	@uv run ty check

ty: type-check  ## Alias for type-check

check: lint fmt type-check  ## Run all checks except tests

test:  ## Run tests
	@test -f tests/PLAYWRIGHT_FULL.test && uv run playwright install --with-deps chromium 2>/dev/null || true
	@uv run pytest

ci: lint fmt type-check test  ## Run everything

##@ GitHub Actions (Local Testing)

act-check:  ## Check if act is installed
ifndef ACT_INSTALLED
	@echo "act is not installed. Install it from: https://nektosact.com/installation/index.html"
	@exit 1
endif

act-list: act-check  ## List all available GitHub Actions workflows
	@act -l

act-ci: act-check  ## Test CI workflow locally using act
	@act -W .github/workflows/ci.yml

act-health-check: act-check  ## Test health-check workflow locally using act
	@act -W .github/workflows/health-check.yml

act-playwright: act-check  ## Test playwright workflow locally using act
	@act -W .github/workflows/playwright.yml

act-cron: act-check  ## Test cron workflow locally using act
	@act -W .github/workflows/cron.yml

##@ Live Bot Commands
### These all require .env file with the vars set based on .env.example!

cron:  ## Run the cron bot (api_app.py)
	@uv run python -m psrt_ghsa_bot.api_app

playwright:  ## Run playwright bot
	@uv run python -m psrt_ghsa_bot.comment_processor

health-check:  ## Run health check
	@uv run python -m psrt_ghsa_bot.health_check
