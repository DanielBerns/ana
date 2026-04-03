.PHONY: help up down build clean rebuild migrate init test logs

# Default target when you just type 'make'
help:
	@echo "Ana System Management Commands:"
	@echo "  make up       - Start the cluster in the background"
	@echo "  make down     - Stop and remove the containers"
	@echo "  make build    - Rebuild the Docker images"
	@echo "  make clean    - Stop containers AND wipe all data (volumes)"
	@echo "  make rebuild  - Wipe everything and build the cluster from scratch"
	@echo "  make migrate  - Run Alembic database migrations for the Memory Quad-Store"
	@echo "  make init     - Rebuild from scratch AND apply migrations safely"
	@echo "  make test     - Run the end-to-end test script"
	@echo "  make logs     - Tail the logs for all services"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

clean:
	docker compose down -v

rebuild: clean
	docker compose up --build --force-recreate -d

migrate:
	@echo "Applying Quad-Store migrations..."
	cd apps/core/memory && uv run alembic upgrade head
	@echo "Migrations complete!"

init: rebuild
	@echo "Waiting 5 seconds for PostgreSQL to boot before migrating..."
	@sleep 5
	$(MAKE) migrate
	@echo "System initialized and ready!"

test:
	uv run python test_e2e.py "Scrape the news."

logs:
	docker compose logs -f
