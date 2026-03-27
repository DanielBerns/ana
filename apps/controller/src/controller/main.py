from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

from shared.events import (
    PerceptionGathered,
    UserPromptReceived,
    ContextRequested,
    ContextProvided,
    CommandIssued
)
from shared.config import setup_logger, fetch_dynamic_config

# --- Logging Setup ---
logger = setup_logger("controller_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("controller", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the router WITH the fetched URL
router = RabbitRouter(rabbitmq_url)

# ==========================================
# EVENT CONSUMERS & PRODUCERS
# ==========================================

@router.subscriber("perceptions")
async def handle_perception(event: PerceptionGathered):
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("perception_consumed", payload={"uri": event.uri})

    request_event = ContextRequested(
        correlation_id=event.correlation_id,
        query_reference=event.source_url,
        reply_to_topic="context_responses"
    )
    await router.broker.publish(request_event, queue="context_requests")
    log.info("context_requested")

@router.subscriber("user_prompts")
async def handle_user_prompt(event: UserPromptReceived):
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("user_prompt_consumed", payload={"user_id": event.user_id})

    request_event = ContextRequested(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        reply_to_topic="context_responses"
    )
    await router.broker.publish(request_event, queue="context_requests")
    log.info("chat_history_requested")

@router.subscriber("context_responses")
async def handle_context_provided(event: ContextProvided):
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("context_received", payload={"history_items": len(event.history)})

    instruction = "process_data" if not event.user_id else "generate_chat_reply"

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
    async with router.lifespan_context(app):
        logger.info("controller_startup_complete")
        yield

app = FastAPI(lifespan=lifespan, title="Ana Controller Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    return {
        "status": "healthy",
        "component": "controller",
        "active_config": DYNAMIC_CONFIG
    }
