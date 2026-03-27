import os
import httpx
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our shared data contracts
from shared.events import (
    PerceptionGathered,
    UserPromptReceived,
    ContextRequested,
    ContextProvided,
    CommandIssued
)

# --- Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("controller_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
# This is the ONLY hardcoded variable allowed. In production, this is injected via an environment variable.
CONFIGURATOR_URL = os.getenv("CONFIGURATOR_URL", "http://localhost:8005/config/controller")

# 1. Fetch config synchronously on module load using httpx
try:
    logger.info("fetching_configuration", payload={"url": CONFIGURATOR_URL})
    with httpx.Client(timeout=5.0) as client:
        response = client.get(CONFIGURATOR_URL)
        response.raise_for_status()
        DYNAMIC_CONFIG = response.json()
    logger.info("config_fetched_successfully")
except Exception as e:
    logger.error("configurator_unreachable", payload={"error": str(e)})
    raise RuntimeError(f"Cannot start Controller without configuration from {CONFIGURATOR_URL}") from e

rabbitmq_url = DYNAMIC_CONFIG.get("rabbitmq_url")
if not rabbitmq_url:
    raise RuntimeError("Configuration missing 'rabbitmq_url'")

# 2. Initialize the router WITH the fetched URL
router = RabbitRouter(rabbitmq_url)

# ==========================================
# EVENT CONSUMERS & PRODUCERS
# ==========================================

@router.subscriber("perceptions")
async def handle_perception(event: PerceptionGathered):
    """
    Consumes autonomous scraping events.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("perception_consumed", payload={"uri": event.uri})

    # 1. We need history/context before making a decision.
    # We publish a request to the Memory component.
    request_event = ContextRequested(
        correlation_id=event.correlation_id,
        query_reference=event.source_url,
        reply_to_topic="context_responses"
    )

    await router.broker.publish(request_event, queue="context_requests")
    log.info("context_requested")

@router.subscriber("user_prompts")
async def handle_user_prompt(event: UserPromptReceived):
    """
    Consumes chat messages from the Proxy Website.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("user_prompt_consumed", payload={"user_id": event.user_id})

    # Request the user's specific chat history from Memory
    request_event = ContextRequested(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        reply_to_topic="context_responses"
    )

    await router.broker.publish(request_event, queue="context_requests")
    log.info("chat_history_requested")

@router.subscriber("context_responses")
async def handle_context_provided(event: ContextProvided):
    """
    Consumes the history returned by the Memory component, makes a decision,
    and issues a Command to the Actor.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("context_received", payload={"history_items": len(event.history)})

    # --- HEXAGONAL ARCHITECTURE DOMAIN LOGIC GOES HERE ---
    # In a mature system, you might use settings from DYNAMIC_CONFIG here
    # (e.g., maximum retries, threshold values, or AI model parameters).

    instruction = "process_data" if not event.user_id else "generate_chat_reply"

    # Issue the command to the Actor
    command = CommandIssued(
        correlation_id=event.correlation_id,
        instruction=instruction,
        user_id=event.user_id,
        context_data={"mock_decision": "success"}
    )

    await router.broker.publish(command, queue="commands")
    log.info("command_issued", payload={"instruction": instruction})


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the FastStream context."""
    # FastStream's lifespan_context handles the RabbitMQ connection automatically using the URL we passed above!
    async with router.lifespan_context(app):
        logger.info("controller_startup_complete")
        yield

# Initialize the FastAPI app and attach the FastStream router
app = FastAPI(lifespan=lifespan, title="Ana Controller Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "controller",
        "active_config": DYNAMIC_CONFIG
    }
