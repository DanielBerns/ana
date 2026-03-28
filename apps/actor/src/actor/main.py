import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our strictly typed domain contracts and shared utilities
from shared.events import BaseEvent, CommandIssued, ActionRequired, TaskCompleted
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost

# --- Logging Setup ---
logger = setup_logger("actor_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("actor", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the FastStream router
router = RabbitRouter(rabbitmq_url)

# ==========================================
# 1. THE COMPONENT HOST
# ==========================================
class ActorHost:
    """
    Concrete implementation of ComponentHost for the Actor.
    """
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = ActorHost(router)


# ==========================================
# 2. EVENT HANDLERS (Adapters)
# ==========================================
class CommandExecutionHandler:
    """
    Listens for CommandIssued events, executes the encapsulated work,
    and emits the resulting Actions and TaskCompleted events.
    """
    def __init__(self, default_timeout: int):
        self.timeout = default_timeout
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("commands", self)

    async def handle(self, command: CommandIssued) -> None:
        if not self._host:
            raise RuntimeError("CommandExecutionHandler not registered")

        log = logger.bind(correlation_id=command.correlation_id)
        log.info("command_received", payload={"instruction": command.instruction})

        # --- ENCAPSULATED DOMAIN LOGIC GOES HERE ---
        # Mocking work using the dynamic config timeout
        await asyncio.sleep(self.timeout)

        try:
            if command.instruction == "generate_chat_reply":
                # 1. We did the work. Now we tell the Interface to reply to the user.
                action = ActionRequired(
                    correlation_id=command.correlation_id,
                    action_type="reply_to_chat",
                    payload="Hello! I have processed your request successfully.",
                    user_id=command.user_id
                )
                await self._host.publish(action, queue="actions")
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
            await self._host.publish(completion_event, queue="task_results")
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
            await self._host.publish(failure_event, queue="task_results")


# ==========================================
# 3. INSTANTIATION & APP LIFECYCLE
# ==========================================

# Instantiate the execution handler
command_handler = CommandExecutionHandler(
    default_timeout=DYNAMIC_CONFIG.get("default_timeout_seconds", 1)
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Register our domains/adapters to the Host
    await command_handler.register(host)

    # 2. Start the messaging lifecycle
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
