# ==========================================
# ANA SYSTEM MAKEFILE
# ==========================================

.PHONY: sync up down run-interface run-store run-controller run-actor run-memory run-inspector run-configurator

# Default instance name if not provided (e.g., make run-controller INSTANCE=prod-1)
INSTANCE ?= devel

# --- Environment & Dependencies ---
sync:
	@echo "Syncing dependencies with uv..."
	uv sync

# --- Infrastructure ---
provision:
	@echo "Provisioning databases and queues for instance: $(INSTANCE)..."
	./provision.sh $(INSTANCE)

up:
	@echo "Starting RabbitMQ and PostgreSQL..."
	docker compose up -d

down:
	@echo "Stopping infrastructure..."
	docker compose down

# --- Component Runners ---
# Note: Run each of these in a separate terminal tab!
run-configurator:
	@echo "Starting Configurator (Port 8005) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.configurator.src.configurator.main:app --reload --port 8005

run-interface:
	@echo "Starting Interface (Port 8000) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.interface.src.interface.main:app --reload --port 8000

run-store:
	@echo "Starting Store (Port 8001) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.store.src.store.main:app --reload --port 8001

run-controller:
	@echo "Starting Controller (Port 8002) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.controller.src.controller.main:app --reload --port 8002

run-actor:
	@echo "Starting Actor (Port 8003) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.actor.src.actor.main:app --reload --port 8003

run-memory:
	@echo "Starting Memory (Port 8004) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.memory.src.memory.main:app --reload --port 8004

run-inspector:
	@echo "Starting Inspector (Port 8006) for instance: $(INSTANCE)..."
	ANA_INSTANCE=$(INSTANCE) uv run uvicorn apps.inspector.src.inspector.main:app --reload --host 0.0.0.0 --port 8006
