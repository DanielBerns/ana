import os
import uuid
from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI
from pydantic import BaseModel
from faststream.rabbit.fastapi import RabbitRouter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import our strictly typed domain contracts and shared utilities
from shared.events import (
    UserPromptReceived, ActionRequired, PerceptionGathered,
    ConfigurationUpdated, SystemFatalError, BaseEvent
)
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, EventSource, ComponentHost, Configurable

# --- Logging Setup ---
logger = setup_logger("interface_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (BOOT)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("interface", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the FastStream router
router = RabbitRouter(rabbitmq_url)

class InterfaceHost:
    """Concrete implementation of ComponentHost."""
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = InterfaceHost(router)


# ==========================================
# ADAPTERS (Event Sources & Handlers)
# ==========================================
class ScrapingEventSource:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.scheduler = AsyncIOScheduler()
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        # Validates and sets operational config
        self.enabled = params.get("enabled", True)
        self.interval = int(params["interval_minutes"]) # Raises KeyError/ValueError if bad
        self.store_api_url = params["store_api_url"]

        # If already running, reschedule the job with the new interval
        if self.scheduler.running and self.enabled:
            self.scheduler.reschedule_job('scrape_job', trigger='interval', minutes=self.interval)
            logger.info("scraping_source_rescheduled", payload={"new_interval": self.interval})

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component

    async def start(self) -> None:
        if not self._host:
            raise RuntimeError("ScrapingEventSource not registered")
        self.scheduler.add_job(self._scrape, 'interval', minutes=self.interval, id='scrape_job')
        self.scheduler.start()

    async def stop(self) -> None:
        self.scheduler.shutdown()

    async def _scrape(self):
        if not self.enabled:
            return # Soft-toggle check

        correlation_id = str(uuid.uuid4())
        log = logger.bind(correlation_id=correlation_id)

        source_url = "https://example.com/news"
        uri = f"{self.store_api_url}/mock-{uuid.uuid4().hex[:8]}.html"

        event = PerceptionGathered(
            correlation_id=correlation_id,
            source_url=source_url,
            uri=uri
        )
        await self._host.publish(event, queue="perceptions")
        log.info("perception_published", payload={"uri": uri})


class ProxyActionHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.proxy_url = params["proxy_url"] # Raises KeyError if missing

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("actions", self)

    async def handle(self, event: ActionRequired) -> None:
        if not self.enabled:
            return # Silently drop/ack the message if disabled at runtime

        log = logger.bind(correlation_id=event.correlation_id)
        if event.action_type == "reply_to_chat" and event.user_id:
            payload = {"user_id": event.user_id, "reply": event.payload}
            log.info("pushed_reply_to_proxy", payload={"proxy_url": self.proxy_url, "data": payload})


# ==========================================
# SYSTEM LIFECYCLE HANDLER
# ==========================================
class SystemHandler:
    """Listens for ConfigurationUpdates and applies them to registered configurables."""
    def __init__(self, component_name: str, registry: dict[str, Configurable]):
        self.component_name = component_name
        self.registry = registry
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        # In a real system, this should be a fan-out exchange so ALL components hear it
        await host_component.subscribe("system.config_updates", self)

    async def handle(self, event: ConfigurationUpdated) -> None:
        if event.target_component not in (self.component_name, "all"):
            return

        log = logger.bind(correlation_id=event.correlation_id)
        log.info("applying_new_configuration")

        try:
            # Apply new config to sources
            for name, config_data in event.new_configuration.get("event_sources", {}).items():
                if name in self.registry:
                    self.registry[name].update_config(config_data)

            # Apply new config to handlers
            for name, config_data in event.new_configuration.get("event_handlers", {}).items():
                if name in self.registry:
                    self.registry[name].update_config(config_data)

            log.info("configuration_applied_successfully")

        except Exception as e:
            log.fatal("invalid_configuration_received", payload={"error": str(e)})

            # Emit the death cry
            fatal_event = SystemFatalError(
                correlation_id=event.correlation_id,
                component=self.component_name,
                error_reason=str(e),
                bad_configuration=event.new_configuration
            )
            await self._host.publish(fatal_event, queue="system.fatal_errors")

            # Force kill the container/process
            os._exit(1)


# ==========================================
# INSTANTIATION & APP LIFECYCLE
# ==========================================
# Instantiate from the dynamic config we got at boot
source_config = DYNAMIC_CONFIG.get("event_sources", {}).get("ScrapingEventSource", {})
handler_config = DYNAMIC_CONFIG.get("event_handlers", {}).get("ProxyActionHandler", {})

scraping_source = ScrapingEventSource(source_config)
proxy_handler = ProxyActionHandler(handler_config)

# The Registry maps the YAML string names to the active Python objects
configurable_registry: dict[str, Configurable] = {
    "ScrapingEventSource": scraping_source,
    "ProxyActionHandler": proxy_handler
}

system_handler = SystemHandler("interface", configurable_registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register adapters
    await proxy_handler.register(host)
    await scraping_source.register(host)
    await system_handler.register(host)

    async with router.lifespan_context(app):
        await scraping_source.start()
        logger.info("interface_startup_complete")
        yield
        await scraping_source.stop()

app = FastAPI(lifespan=lifespan, title="Ana Interface Component")
app.include_router(router)


# ==========================================
# 4. HTTP ROUTES (Inbound Triggers)
# ==========================================
class ProxyChatPayload(BaseModel):
    user_id: str
    message: str

@app.post("/webhook/chat")
async def receive_chat_from_proxy(payload: ProxyChatPayload):
    """
    HTTP Webhook. This essentially acts as a direct EventSource trigger
    that uses the Host to publish an event, completely bypassing RabbitMQ specifics.
    """
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)
    log.info("user_prompt_received", payload={"user_id": payload.user_id})

    event = UserPromptReceived(
        correlation_id=correlation_id,
        user_id=payload.user_id,
        text=payload.message
    )

    await host.publish(event, queue="user_prompts")
    log.info("published_to_broker")

    return {"status": "accepted", "correlation_id": correlation_id}


@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "interface",
        "scheduler_running": scraping_source.scheduler.running,
        "active_config": DYNAMIC_CONFIG
    }
