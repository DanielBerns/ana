.PHONY: help up down build clean rebuild init test logs

# Default target when you just type 'make'
help:
	@echo "Ana System Management Commands:"
	@echo "  make up       - Start the cluster in the background"
	@echo "  make down     - Stop and remove the containers"
	@echo "  make build    - Rebuild the Docker images"
	@echo "  make clean    - Stop containers AND wipe all data (volumes)"
	@echo "  make rebuild  - Wipe everything and build the cluster from scratch"
	@echo "  make init     - Rebuild from scratch (migrations run automatically on container startup)"
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

init: rebuild
	@echo "System initialized! Containers are booting and running their own migrations."

test:
	uv run python test_e2e.py "Scrape the news."

logs:
	docker compose logs -f
