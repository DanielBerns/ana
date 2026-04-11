.PHONY: install format lint test run db-init init reset backup config-generate

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
	# We will expand this to run FastStream and Rocketry concurrently
	# uv run faststream run src.main:app

# ==========================================
# OFFLINE CLI ADMINISTRATION
# ==========================================

db-init:
	@echo "Applying EdgeDB migrations..."
	# edgedb migrate

init:
	uv run python -m cli.main init

reset:
	uv run python -m cli.main reset

backup:
	uv run python -m cli.main backup

config-generate:
	uv run python -m cli.main config generate

config-update:
	uv run python -m cli.main config update
