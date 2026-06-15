.DEFAULT_GOAL:=help
.ONESHELL:

help: ## Display this help text for Makefile
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

upgrade:  ## Upgrade all dependencies to the latest stable versions
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

test:  ## Run tests
	@uv run pytest

ci: lint fmt type-check test  ## Run everything

app:  ## Run the app
	@uv run python src/psrt_ghsa_bot/app.py