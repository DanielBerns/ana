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
# DYNAMIC CONFIGURATION STATE
# ==========================================
# This is the ONLY hardcoded variable allowed. In production, this would be injected via an environment variable.
CONFIGURATOR_URL = os.getenv("CONFIGURATOR_URL", "http://localhost:8005/config/actor")

# Global dictionary to hold the config fetched during startup
DYNAMIC_CONFIG = {}

# --- FastStream Router Setup ---
# Initialize the router WITHOUT a hardcoded RabbitMQ URL
router = RabbitRouter()

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

    # Let's use a dynamic config variable for our mocked work timeout!
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
    """Fetches dynamic config and manages the startup of the Broker connection."""
    global DYNAMIC_CONFIG

    # 1. Fetch Dynamic Configuration from the Configurator Component
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(CONFIGURATOR_URL)
            response.raise_for_status()
            DYNAMIC_CONFIG = response.json()
            logger.info("config_fetched_successfully", payload={"configurator_url": CONFIGURATOR_URL})
        except Exception as e:
            logger.error("configurator_unreachable", payload={"error": str(e)})
            raise RuntimeError(f"Cannot start Actor without configuration from {CONFIGURATOR_URL}") from e

    # 2. Connect to the Event Broker dynamically using the fetched URL
    rabbitmq_url = DYNAMIC_CONFIG.get("rabbitmq_url")
    if not rabbitmq_url:
        raise RuntimeError("Configuration missing 'rabbitmq_url'")

    await router.broker.connect(rabbitmq_url)

    # 3. Start the FastStream context
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
