# ==========================================
# ANA SYSTEM MAKEFILE
# ==========================================

.PHONY: sync up down run-interface run-store run-controller run-actor

# --- Environment & Dependencies ---
sync:
	@echo "Syncing dependencies with uv..."
	uv sync

# --- Infrastructure ---
up:
	@echo "Starting RabbitMQ and PostgreSQL..."
	docker compose up -d

down:
	@echo "Stopping infrastructure..."
	docker compose down

# --- Component Runners ---
# Note: Run each of these in a separate terminal tab!

run-configurator:
	@echo "Starting Configurator (Port 8005)..."
	uv run uvicorn apps.configurator.src.configurator.main:app --reload --port 8005

run-interface:
	@echo "Starting Interface (Port 8000)..."
	uv run uvicorn apps.interface.src.interface.main:app --reload --port 8000

run-store:
	@echo "Starting Store (Port 8001)..."
	uv run uvicorn apps.store.src.store.main:app --reload --port 8001

run-controller:
	@echo "Starting Controller (Port 8002)..."
	uv run uvicorn apps.controller.src.controller.main:app --reload --port 8002

run-actor:
	@echo "Starting Actor (Port 8003)..."
	uv run uvicorn apps.actor.src.actor.main:app --reload --port 8003

run-memory:
	@echo "Starting Memory (Port 8004)..."
	uv run uvicorn apps.memory.src.memory.main:app --reload --port 8004

run-inspector:
	@echo "Starting Inspector (Port 8006)..."
	uv run uvicorn apps.inspector.src.inspector.main:app --reload --port 8006
