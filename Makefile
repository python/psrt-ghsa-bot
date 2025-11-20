.DEFAULT_GOAL:=help
.ONESHELL:

help: ## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

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

app:  ## Run the app
	@uv run python app.py

### --- Bot Things
### These all reequire .env file with the vars set based on .env.example!
cron-run:  ## Run the cron bot (app.py)
	@uv run python -m psrt_ghsa_bot.app

playwright-run:  ## Run playwright bot
	@uv run python -m psrt_ghsa_bot.comment_processor

health-check:  ## Run health check
	@uv run python -m psrt_ghsa_bot.health_check
