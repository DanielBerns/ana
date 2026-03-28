import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from faststream.rabbit.fastapi import RabbitRouter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import our strictly typed domain contracts and shared utilities
from shared.events import UserPromptReceived, ActionRequired, PerceptionGathered, BaseEvent
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, EventSource, ComponentHost

# --- Logging Setup ---
logger = setup_logger("interface_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("interface", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the FastStream router
router = RabbitRouter(rabbitmq_url)

# ==========================================
# 1. THE COMPONENT HOST
# ==========================================
class InterfaceHost:
    """
    Concrete implementation of ComponentHost.
    It bridges our domain Handlers/Sources to the FastStream RabbitMQ router.
    """
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        # FastStream's subscriber can be used dynamically as a decorator wrapper!
        # It automatically parses the Pydantic type defined in `handler.handle`
        self.router.subscriber(topic)(handler.handle)

# Instantiate the Host
host = InterfaceHost(router)


# ==========================================
# 2. EVENT SOURCES & HANDLERS (Domain/Adapters)
# ==========================================
class ScrapingEventSource:
    """EventSource: Runs periodically and emits PerceptionGathered events."""
    def __init__(self, interval_minutes: int, store_api_url: str):
        self.interval = interval_minutes
        self.store_api_url = store_api_url
        self._host: ComponentHost | None = None
        self.scheduler = AsyncIOScheduler()

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component

    async def start(self) -> None:
        if not self._host:
            raise RuntimeError("ScrapingEventSource not registered")
        self.scheduler.add_job(self._scrape, 'interval', minutes=self.interval)
        self.scheduler.start()
        logger.info("scraping_source_started", payload={"interval": self.interval})

    async def stop(self) -> None:
        self.scheduler.shutdown()

    async def _scrape(self):
        correlation_id = str(uuid.uuid4())
        log = logger.bind(correlation_id=correlation_id)
        log.info("autonomous_scrape_started")

        # Completely encapsulated scraping logic
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
    """EventHandler: Listens for ActionRequired events and pushes to an external Proxy."""
    def __init__(self, proxy_url: str):
        self.proxy_url = proxy_url
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        # Tell the host we want to listen to the "actions" queue
        await host_component.subscribe("actions", self)

    async def handle(self, event: ActionRequired) -> None:
        log = logger.bind(correlation_id=event.correlation_id)
        log.info("action_required_consumed", payload={"action_type": event.action_type})

        if event.action_type == "reply_to_chat" and event.user_id:
            try:
                payload = {"user_id": event.user_id, "reply": event.payload}
                # Encapsulated HTTP request (commented out to match original mock)
                # async with httpx.AsyncClient() as client:
                #     await client.post(self.proxy_url, json=payload)
                log.info("pushed_reply_to_proxy", payload={"proxy_url": self.proxy_url, "data": payload})
            except Exception as e:
                log.error("proxy_push_failed", payload={"error": str(e)})


# ==========================================
# 3. INSTANTIATION & APP LIFECYCLE
# ==========================================
scraping_source = ScrapingEventSource(
    interval_minutes=DYNAMIC_CONFIG.get("scraping_interval_minutes", 10),
    store_api_url=DYNAMIC_CONFIG.get("store_api_url", "http://localhost:8001/files")
)

proxy_handler = ProxyActionHandler(
    proxy_url=DYNAMIC_CONFIG.get("proxy_website_url", "http://localhost:3000/webhook")
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Register our domains to the Host
    await proxy_handler.register(host)
    await scraping_source.register(host)

    # 2. FastStream handles the RabbitMQ connection lifecycle
    async with router.lifespan_context(app):
        # 3. Start our autonomous sources
        await scraping_source.start()
        logger.info("interface_startup_complete")

        yield # Application is running

        # 4. Graceful teardown
        await scraping_source.stop()

# Initialize the FastAPI app and attach the FastStream router
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
