import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from faststream.rabbit.fastapi import RabbitRouter

from shared.events import UserPromptReceived, ConfigurationUpdated, SystemFatalError, BaseEvent
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

# Import our extracted adapters
from .adapters.sources import ScrapingEventSource, RSSEventSource
from .adapters.handlers import ProxyActionHandler

logger = setup_logger("interface_component")
DYNAMIC_CONFIG = fetch_dynamic_config("interface")
rabbitmq_url = DYNAMIC_CONFIG["global"]["rabbitmq_url"]
router = RabbitRouter(rabbitmq_url)

class InterfaceHost:
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router
    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)
    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = InterfaceHost(router)

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
            for name, config_data in event.new_configuration.get("event_sources", {}).items():
                if name in self.registry: self.registry[name].update_config(config_data)
            for name, config_data in event.new_configuration.get("event_handlers", {}).items():
                if name in self.registry: self.registry[name].update_config(config_data)
        except Exception as e:
            await self._host.publish(SystemFatalError(
                correlation_id=event.correlation_id, component=self.component_name,
                error_reason=str(e), bad_configuration=event.new_configuration
            ), queue="system.fatal_errors")
            os._exit(1)

# App Lifecycle
# Fetch the top-level parent dictionaries
source_config = DYNAMIC_CONFIG.get("event_sources", {})
handler_config = DYNAMIC_CONFIG.get("event_handlers", {})

# Extract the correct child blocks
scraping_source = ScrapingEventSource(source_config.get("ScrapingEventSource", {}))
rss_source = RSSEventSource(source_config.get("RSSEventSource", {}))
proxy_handler = ProxyActionHandler(handler_config.get("ProxyActionHandler", {}))


registry: dict[str, Configurable] = {
    "ScrapingEventSource": scraping_source,
    "RSSEventSource": rss_source,
    "ProxyActionHandler": proxy_handler
}
system_handler = SystemHandler("interface", registry)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await proxy_handler.register(host)
    await scraping_source.register(host)
    await rss_source.register(host)
    await system_handler.register(host)
    await scraping_source.start()
    await rss_source.start()
    yield
    await scraping_source.stop()
    await rss_source.stop()

app = FastAPI(lifespan=lifespan, title="Ana Interface Component")
app.include_router(router)

class ProxyChatPayload(BaseModel):
    user_id: str
    message: str

@app.post("/webhook/chat")
async def receive_chat_from_proxy(payload: ProxyChatPayload):
    correlation_id = str(uuid.uuid4())
    event = UserPromptReceived(correlation_id=correlation_id, user_id=payload.user_id, text=payload.message)
    await host.publish(event, queue="user_prompts")
    return {"status": "accepted", "correlation_id": correlation_id}

@app.get("/inspector")
async def inspector_endpoint():
    return {"status": "healthy", "component": "interface", "active_config": DYNAMIC_CONFIG}
