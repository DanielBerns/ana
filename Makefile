# ==========================================
# CONFIGURATION
# ==========================================
.DEFAULT_GOAL := help

.PHONY: help install format lint test run init reset backup config-generate config-update rabbit-up rabbit-down rabbit-logs

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==========================================
# DEVELOPMENT & RUNTIME
# ==========================================

install: ## Install dependencies using uv
	uv sync

format: ## Auto-format code using ruff
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Run linter using ruff
	uv run ruff check .

test: ## Run the test suite with pytest
	uv run pytest tests/ -v

run: ## Start the Ana system
	@echo "Starting Ana..."
	uv run scripts/run.py

# ==========================================
# OFFLINE CLI ADMINISTRATION
# ==========================================

init: ## Initialize the system via CLI
	uv run scripts/cli.py init

reset: ## Reset the system via CLI
	uv run scripts/cli.py reset

backup: ## Trigger a system backup via CLI
	uv run scripts/cli.py backup

config-generate: ## Generate a default configuration file
	uv run scripts/cli.py config generate

config-update: ## Update the system configuration
	uv run scripts/cli.py config update

# ==========================================
# INFRASTRUCTURE (Podman)
# ==========================================

rabbit-up: ## Start RabbitMQ in a Podman container
	@echo "Starting RabbitMQ via Podman..."
	podman run -d --rm --name ana-rabbitmq -p 5672:5672 -p 15672:15672 docker.io/library/rabbitmq:3-management
	@echo "RabbitMQ is running. Management UI available at http://localhost:15672 (guest/guest)"

rabbit-down: ## Stop the RabbitMQ container
	@echo "Stopping RabbitMQ..."
	podman stop ana-rabbitmq

rabbit-logs: ## Tail the RabbitMQ container logs
	podman logs -f ana-rabbitmq
