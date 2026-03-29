import os
from typing import Any
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

from shared.events import CommandIssued, ActionRequired, ConfigurationUpdated, SystemFatalError, BaseEvent
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

from .domain.ports import LlmProvider
from .infrastructure.llm import DummyLlmAdapter

logger = setup_logger("actor_component")

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

class CommandExecutionHandler:
    def __init__(self, config: dict[str, Any], llm_provider: LlmProvider):
        self._host: ComponentHost | None = None
        self.llm = llm_provider
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.system_prompt = params.get("system_prompt", "You are Ana, a helpful AI system.")

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("commands", self)

    async def handle(self, event: CommandIssued) -> None:
        if not self.enabled or event.target_component != "actor":
            return

        log = logger.bind(correlation_id=event.correlation_id, instruction=event.instruction)

        if event.instruction == "generate_chat_reply":
            try:
                payload = event.payload or {}
                history = payload.get("chat_history", [])
                user_id = payload.get("user_id")

                log.info("generating_llm_reply", payload={"history_length": len(history)})

                # Execute the adapter
                reply_text = await self.llm.generate_reply(history, self.system_prompt)

                # Publish the action for Interface & Memory
                action = ActionRequired(
                    correlation_id=event.correlation_id,
                    action_type="reply_to_chat",
                    user_id=user_id,
                    payload=reply_text
                )
                await self._host.publish(action, queue="actions")
                log.info("chat_reply_generated_and_published")

            except Exception as e:
                log.error("llm_generation_failed", payload={"error": str(e)})


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
        try:
            for name, config_data in event.new_configuration.get("event_handlers", {}).items():
                if name in self.registry: self.registry[name].update_config(config_data)
        except Exception as e:
            await self._host.publish(SystemFatalError(correlation_id=event.correlation_id, component=self.component_name, error_reason=str(e), bad_configuration=event.new_configuration), queue="system.fatal_errors")
            os._exit(1)


# App Lifecycle
handler_config = DYNAMIC_CONFIG.get("event_handlers", {})

# Instantiate the port and inject it into the handler
llm_adapter = DummyLlmAdapter()
command_handler = CommandExecutionHandler(handler_config.get("CommandExecutionHandler", {}), llm_adapter)

registry: dict[str, Configurable] = {
    "CommandExecutionHandler": command_handler
}
system_handler = SystemHandler("actor", registry)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await command_handler.register(host)
    await system_handler.register(host)
    logger.info("actor_startup_complete")
    yield

app = FastAPI(lifespan=lifespan, title="Ana Actor Component")
app.include_router(router)

@app.get("/inspector")
async def inspector_endpoint():
    return {"status": "healthy", "component": "actor", "active_config": DYNAMIC_CONFIG}
