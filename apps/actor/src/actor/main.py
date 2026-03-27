import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

from shared.events import CommandIssued, ActionRequired, TaskCompleted
from shared.config import setup_logger, fetch_dynamic_config

# --- Logging Setup ---
logger = setup_logger("actor_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("actor", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the router WITH the fetched URL
router = RabbitRouter(rabbitmq_url)

# ==========================================
# EVENT CONSUMERS & PRODUCERS (Driving & Driven Ports)
# ==========================================

@router.subscriber("commands")
async def handle_command(command: CommandIssued):
    log = logger.bind(correlation_id=command.correlation_id)
    log.info("command_received", payload={"instruction": command.instruction})

    # Use the dynamic config variable for our mocked work timeout!
    timeout = DYNAMIC_CONFIG.get("default_timeout_seconds", 1)
    await asyncio.sleep(timeout)

    try:
        if command.instruction == "generate_chat_reply":
            action = ActionRequired(
                correlation_id=command.correlation_id,
                action_type="reply_to_chat",
                payload="Hello! I have processed your request successfully.",
                user_id=command.user_id
            )
            await router.broker.publish(action, queue="actions")
            log.info("action_required_published", payload={"action_type": action.action_type})

        elif command.instruction == "process_data":
            log.info("data_processed_successfully")

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
    async with router.lifespan_context(app):
        logger.info("actor_startup_complete")
        yield

app = FastAPI(lifespan=lifespan, title="Ana Actor Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    return {
        "status": "healthy",
        "component": "actor",
        "active_config": DYNAMIC_CONFIG
    }
