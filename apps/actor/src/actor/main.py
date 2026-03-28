import os
import asyncio
from typing import Any
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our strictly typed domain contracts and shared utilities
from shared.events import (
    BaseEvent, CommandIssued, ActionRequired, TaskCompleted,
    ConfigurationUpdated, SystemFatalError
)
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

# --- Logging Setup ---
logger = setup_logger("actor_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (BOOT)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("actor", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

router = RabbitRouter(rabbitmq_url)

class ActorHost:
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = ActorHost(router)


# ==========================================
# ADAPTERS (Event Handlers)
# ==========================================
class CommandExecutionHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.timeout = int(params.get("default_timeout_seconds", 1))

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("commands", self)

    async def handle(self, command: CommandIssued) -> None:
        if not self.enabled: return

        log = logger.bind(correlation_id=command.correlation_id)
        log.info("command_received", payload={"instruction": command.instruction})

        # Mocking work using the dynamic timeout parameter
        await asyncio.sleep(self.timeout)

        try:
            if command.instruction == "generate_chat_reply":
                action = ActionRequired(
                    correlation_id=command.correlation_id,
                    action_type="reply_to_chat",
                    payload="Hello! I have processed your request successfully.",
                    user_id=command.user_id
                )
                await self._host.publish(action, queue="actions")

            completion_event = TaskCompleted(
                correlation_id=command.correlation_id, task_name=command.instruction,
                status="success", result_summary="Execution completed without errors."
            )
            await self._host.publish(completion_event, queue="task_results")

        except Exception as e:
            log.error("command_execution_failed", payload={"error": str(e)})
            failure_event = TaskCompleted(
                correlation_id=command.correlation_id, task_name=command.instruction,
                status="failure", result_summary=f"Failed due to error: {str(e)}"
            )
            await self._host.publish(failure_event, queue="task_results")


# ==========================================
# SYSTEM LIFECYCLE HANDLER
# ==========================================
class SystemHandler:
    def __init__(self, component_name: str, registry: dict[str, Configurable]):
        self.component_name = component_name
        self.registry = registry
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("system.config_updates", self)

    async def handle(self, event: ConfigurationUpdated) -> None:
        if event.target_component not in (self.component_name, "all"): return

        log = logger.bind(correlation_id=event.correlation_id)
        try:
            for name, config_data in event.new_configuration.get("event_handlers", {}).items():
                if name in self.registry:
                    self.registry[name].update_config(config_data)
            log.info("configuration_applied_successfully")
        except Exception as e:
            log.fatal("invalid_configuration_received", payload={"error": str(e)})

            fatal_event = SystemFatalError(
                correlation_id=event.correlation_id, component=self.component_name,
                error_reason=str(e), bad_configuration=event.new_configuration
            )
            await self._host.publish(fatal_event, queue="system.fatal_errors")
            os._exit(1)


# ==========================================
# INSTANTIATION & APP LIFECYCLE
# ==========================================
handler_configs = DYNAMIC_CONFIG.get("event_handlers", {})

command_handler = CommandExecutionHandler(handler_configs.get("CommandExecutionHandler", {}))

configurable_registry: dict[str, Configurable] = {
    "CommandExecutionHandler": command_handler
}

system_handler = SystemHandler("actor", configurable_registry)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await command_handler.register(host)
    await system_handler.register(host)

    async with router.lifespan_context(app):
        logger.info("actor_startup_complete")
        yield

app = FastAPI(lifespan=lifespan, title="Ana Actor Component")
app.include_router(router)


@app.get("/inspector")
async def inspector_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "actor",
        "active_config": DYNAMIC_CONFIG
    }
