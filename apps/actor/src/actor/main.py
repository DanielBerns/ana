import os
import asyncio
import httpx
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our shared data contracts
from shared.events import CommandIssued, ActionRequired, TaskCompleted

# --- Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("actor_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
# This is the ONLY hardcoded variable allowed. In production, this is injected via an environment variable.
CONFIGURATOR_URL = os.getenv("CONFIGURATOR_URL", "http://localhost:8005/config/actor")

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
    raise RuntimeError(f"Cannot start Actor without configuration from {CONFIGURATOR_URL}") from e

rabbitmq_url = DYNAMIC_CONFIG.get("rabbitmq_url")
if not rabbitmq_url:
    raise RuntimeError("Configuration missing 'rabbitmq_url'")

# 2. Initialize the router WITH the fetched URL
router = RabbitRouter(rabbitmq_url)

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

    # Use the dynamic config variable for our mocked work timeout!
    timeout = DYNAMIC_CONFIG.get("default_timeout_seconds", 1)
    await asyncio.sleep(timeout)

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
            # For autonomous scraping, we might trigger an internal action.
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
    """Starts the FastStream context."""
    # FastStream's lifespan_context handles the RabbitMQ connection automatically using the URL we passed above!
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
        "active_config": DYNAMIC_CONFIG
    }
