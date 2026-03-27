import os
import uuid
import httpx
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from faststream.rabbit.fastapi import RabbitRouter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import our strictly typed domain contracts
from shared.events import UserPromptReceived, ActionRequired, PerceptionGathered

# --- Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("interface_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE
# ==========================================
CONFIGURATOR_URL = os.getenv("CONFIGURATOR_URL", "http://localhost:8005/config/interface")

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
    raise RuntimeError(f"Cannot start Interface without configuration from {CONFIGURATOR_URL}") from e

rabbitmq_url = DYNAMIC_CONFIG.get("rabbitmq_url")
if not rabbitmq_url:
    raise RuntimeError("Configuration missing 'rabbitmq_url'")

# 2. Initialize the router WITH the fetched URL
router = RabbitRouter(rabbitmq_url)
scheduler = AsyncIOScheduler()


# ==========================================
# A. AUTONOMOUS AGENT (The Cron Scheduler)
# ==========================================
async def autonomous_scraping_job():
    """
    Runs periodically. Scrapes data, uploads the heavy payload to the Store,
    and publishes the Claim Check URI as an event.
    """
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)
    log.info("autonomous_scrape_started")

    source_url = "https://example.com/news"

    try:
        # Dynamically fetch the Store API URL from our configuration state
        store_api_url = DYNAMIC_CONFIG.get("store_api_url", "http://localhost:8001/files")

        # Mocking the Store response for now.
        uri = f"{store_api_url}/mock-{uuid.uuid4().hex[:8]}.html"

        event = PerceptionGathered(
            correlation_id=correlation_id,
            source_url=source_url,
            uri=uri
        )
        await router.broker.publish(event, queue="perceptions")
        log.info("perception_published", payload={"uri": uri, "source": source_url})

    except Exception as e:
        log.error("scraping_failed", payload={"error": str(e)})


# ==========================================
# B. CHAT BRIDGE (Inbound & Outbound)
# ==========================================
class ProxyChatPayload(BaseModel):
    user_id: str
    message: str

@router.post("/webhook/chat")
async def receive_chat_from_proxy(payload: ProxyChatPayload):
    """
    Inbound adapter: Translates Proxy HTTP POST into an internal Event.
    """
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)
    log.info("user_prompt_received", payload={"user_id": payload.user_id})

    event = UserPromptReceived(
        correlation_id=correlation_id,
        user_id=payload.user_id,
        text=payload.message
    )

    await router.broker.publish(event, queue="user_prompts")
    log.info("published_to_broker")

    return {"status": "accepted", "correlation_id": correlation_id}


@router.subscriber("actions")
async def handle_action_required(action: ActionRequired):
    """
    Outbound adapter: Listens for commands from the Actor and pushes back to Proxy.
    """
    log = logger.bind(correlation_id=action.correlation_id)
    log.info("action_required_consumed", payload={"action_type": action.action_type})

    if action.action_type == "reply_to_chat" and action.user_id:
        try:
            proxy_url = DYNAMIC_CONFIG.get("proxy_website_url")
            payload = {"user_id": action.user_id, "reply": action.payload}

            # async with httpx.AsyncClient() as client:
            #     await client.post(proxy_url, json=payload)

            log.info("pushed_reply_to_proxy", payload={"proxy_url": proxy_url, "data": payload})
        except Exception as e:
            log.error("proxy_push_failed", payload={"error": str(e)})


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the FastStream context and Scheduler."""

    # FastStream's lifespan_context handles the RabbitMQ connection automatically!
    async with router.lifespan_context(app):

        interval = DYNAMIC_CONFIG.get("scraping_interval_minutes", 10)
        scheduler.add_job(autonomous_scraping_job, 'interval', minutes=interval)
        scheduler.start()

        logger.info("interface_startup_complete", payload={"scraping_interval": interval})

        yield # The application is now running and processing requests/events

        # Shutdown gracefully
        scheduler.shutdown()

# Initialize the FastAPI app and attach the FastStream router
app = FastAPI(lifespan=lifespan, title="Ana Interface Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "interface",
        "scheduler_running": scheduler.running,
        "jobs_scheduled": len(scheduler.get_jobs()),
        "active_config": DYNAMIC_CONFIG
    }
