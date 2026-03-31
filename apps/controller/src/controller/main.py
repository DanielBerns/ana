import os
from typing import Any
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

from shared.events import (
    BaseEvent, PerceptionGathered, UserPromptReceived, ContextRequested,
    ContextProvided, CommandIssued, ConfigurationUpdated, SystemFatalError
)
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

from .domain.rules import RuleEngine

logger = setup_logger("controller_component")

DYNAMIC_CONFIG = fetch_dynamic_config("controller")
rabbitmq_url = DYNAMIC_CONFIG["global"]["rabbitmq_url"]

router = RabbitRouter(rabbitmq_url)

class ControllerHost:
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = ControllerHost(router)

class PerceptionHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("perceptions", self)

    async def handle(self, event: PerceptionGathered) -> None:
        if not self.enabled: return

        log = logger.bind(correlation_id=event.correlation_id)
        request_event = ContextRequested(
            correlation_id=event.correlation_id,
            query_reference=event.source_url,
            reply_to_topic="context_responses"
        )
        await self._host.publish(request_event, queue="context_requests")
        log.info("context_requested")

class UserPromptHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("user_prompts", self)

    async def handle(self, event: UserPromptReceived) -> None:
        if not self.enabled: return

        log = logger.bind(correlation_id=event.correlation_id)
        request_event = ContextRequested(
            correlation_id=event.correlation_id,
            user_id=event.user_id,
            query_reference=event.text,
            reply_to_topic="context_responses"
        )
        await self._host.publish(request_event, queue="context_requests")
        log.info("chat_history_requested")

class ContextProvidedHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.rule_engine = RuleEngine(config.get("rules", {}))

    def update_config(self, params: dict[str, Any]) -> None:
        self.rule_engine.update_config(params.get("rules", {}))

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await self.rule_engine.register(host_component)
        await host_component.subscribe("memory.context_provided", self)

    # FIX: Explicit typing of ContextProvided to maintain Pydantic schema contract
    async def handle(self, event: ContextProvided) -> None:
        log = logger.bind(correlation_id=event.correlation_id)
        await self.rule_engine.evaluate_all(event)
        log.info("context_evaluated_by_active_rules")

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

handler_configs = DYNAMIC_CONFIG.get("event_handlers", {})

perception_handler = PerceptionHandler(handler_configs.get("PerceptionHandler", {}))
user_prompt_handler = UserPromptHandler(handler_configs.get("UserPromptHandler", {}))
context_provided_handler = ContextProvidedHandler(handler_configs.get("ContextProvidedHandler", {}))

configurable_registry: dict[str, Configurable] = {
    "PerceptionHandler": perception_handler,
    "UserPromptHandler": user_prompt_handler,
    "ContextProvidedHandler": context_provided_handler
}

system_handler = SystemHandler("controller", configurable_registry)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await perception_handler.register(host)
    await user_prompt_handler.register(host)
    await context_provided_handler.register(host)
    await system_handler.register(host)

    logger.info("controller_startup_complete")
    yield

app = FastAPI(lifespan=lifespan, title="Ana Controller Component")
app.include_router(router)

@app.get("/inspector")
async def inspector_endpoint():
    return {
        "status": "healthy",
        "component": "controller",
        "active_config": DYNAMIC_CONFIG,
        "active_rules": [type(r).__name__ for r in context_provided_handler.rule_engine.rules]
    }
