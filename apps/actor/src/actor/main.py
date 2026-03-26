import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our shared data contracts
from shared.events import CommandIssued, ActionRequired, TaskCompleted

# --- Configuration & Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("actor_component")

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"

# --- FastStream Router Setup ---
# Using RabbitRouter so we can expose the HTTP diagnostic API alongside event consumers
router = RabbitRouter(RABBITMQ_URL)

# ==========================================
# EVENT CONSUMERS & PRODUCERS (Driving & Driven Ports)
# ==========================================

@router.subscriber("commands")
async def handle_command(command: CommandIssued):
    """
    Inbound adapter: Listens for instructions from the Controller.
    """
    # Bind the correlation_id to all logs in this workflow execution
    log = logger.bind(correlation_id=command.correlation_id)
    log.info("command_received", payload={"instruction": command.instruction})

    # --- HEXAGONAL ARCHITECTURE DOMAIN LOGIC GOES HERE ---
    # This is where the actual "work" happens (e.g., querying an external API,
    # processing data, formatting a response).
    # We will mock a slight delay to represent work being done.
    await asyncio.sleep(1)

    try:
        if command.instruction == "generate_chat_reply":
            # 1. We did the work. Now we tell the Interface to reply to the user.
            action = ActionRequired(
                correlation_id=command.correlation_id,
                action_type="reply_to_chat",
                payload="Hello! I have processed your request successfully.",
                user_id=command.user_id
            )
            await router.broker.publish(action, queue="actions")
            log.info("action_required_published", payload={"action_type": action.action_type})

        elif command.instruction == "process_data":
            # For autonomous scraping, we might not need to chat back to a user,
            # but we might trigger an internal action.
            log.info("data_processed_successfully")

        # 2. Regardless of the instruction, we MUST publish a TaskCompleted event
        # so the Memory component can log the operational record.
        completion_event = TaskCompleted(
            correlation_id=command.correlation_id,
            task_name=command.instruction,
            status="success",
            result_summary="Execution completed without errors."
        )
        await router.broker.publish(completion_event, queue="task_results")
        log.info("task_completed_published", payload={"status": "success"})

    except Exception as e:
        log.error("command_execution_failed", payload={"error": str(e)})

        # Publish a failure record to Memory
        failure_event = TaskCompleted(
            correlation_id=command.correlation_id,
            task_name=command.instruction,
            status="failure",
            result_summary=f"Failed due to error: {str(e)}"
        )
        await router.broker.publish(failure_event, queue="task_results")


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the startup and shutdown of the Broker connection."""
    async with router.lifespan_context(app):
        logger.info("actor_startup_complete")
        yield

# Initialize the FastAPI app and attach the FastStream router
app = FastAPI(lifespan=lifespan, title="Ana Actor Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "actor",
        "broker_connected": True
    }
