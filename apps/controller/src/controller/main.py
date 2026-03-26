import uuid
import structlog
from faststream import FastStream
from faststream.rabbit import RabbitBroker

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
        structlog.processors.JSONRenderer() #
    ]
)
logger = structlog.get_logger("controller_component")

# --- Broker Setup ---
broker = RabbitBroker("amqp://guest:guest@localhost:5672/")
app = FastStream(broker)

# ==========================================
# EVENT CONSUMERS & PRODUCERS
# ==========================================

@broker.subscriber("perceptions")
async def handle_perception(event: PerceptionGathered):
    """
    Consumes autonomous scraping events.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("perception_consumed", payload={"uri": event.uri})

    # 1. We need history/context before making a decision.
    # We publish a request to the Memory component.
    request_event = ContextRequested(
        correlation_id=event.correlation_id, # Pass the trace ID along!
        query_reference=event.source_url,
        reply_to_topic="context_responses"
    )

    await broker.publish(request_event, queue="context_requests")
    log.info("context_requested")

@broker.subscriber("user_prompts")
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

    await broker.publish(request_event, queue="context_requests")
    log.info("chat_history_requested")

@broker.subscriber("context_responses")
async def handle_context_provided(event: ContextProvided):
    """
    Consumes the history returned by the Memory component, makes a decision,
    and issues a Command to the Actor.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("context_received", payload={"history_items": len(event.history)})

    # --- HEXAGONAL ARCHITECTURE DOMAIN LOGIC GOES HERE ---
    # Here is where you would evaluate the Perception/Prompt + Context
    # (e.g., passing it to an LLM, a rules engine, etc.)
    # For now, we mock the decision:
    instruction = "process_data" if not event.user_id else "generate_chat_reply"

    # Issue the command to the Actor
    command = CommandIssued(
        correlation_id=event.correlation_id,
        instruction=instruction,
        user_id=event.user_id,
        context_data={"mock_decision": "success"}
    )

    await broker.publish(command, queue="commands")
    log.info("command_issued", payload={"instruction": instruction})

@app.after_startup
async def startup():
    logger.info("controller_startup_complete")
