.PHONY: install format lint test run db-init init reset backup config-generate rabbit-up rabbit-down rabbit-logs

# ==========================================
# DEVELOPMENT & RUNTIME
# ==========================================

install:
	uv sync

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .

test:
	uv run pytest tests/ -v

run:
	@echo "Starting Ana..."
	uv run scripts/run.py

# ==========================================
# OFFLINE CLI ADMINISTRATION
# ==========================================

db-init:
	@echo "Applying EdgeDB migrations..."
	# edgedb migrate

init:
	uv run scripts/cli.py init

reset:
	uv run scripts/cli.py reset

backup:
	uv run scripts/cli.py backup

config-generate:
	uv run scripts/cli.py config generate

config-update:
	uv run scripts/cli.py config update

# ==========================================
# Rabbit up, down, and logs
# ==========================================

rabbit-up:
	@echo "Starting RabbitMQ via Podman..."
	podman run -d --rm --name ana-rabbitmq -p 5672:5672 -p 15672:15672 docker.io/library/rabbitmq:3-management
	@echo "RabbitMQ is running. Management UI available at http://localhost:15672 (guest/guest)"

rabbit-down:
	@echo "Stopping RabbitMQ..."
	podman stop ana-rabbitmq

rabbit-logs:
	podman logs -f ana-rabbitmq
