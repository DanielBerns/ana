import asyncio
import uuid
import httpx
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from faststream.rabbit.fastapi import RabbitRouter
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import our strictly typed domain contracts
from shared.events import UserPromptReceived, ActionRequired, PerceptionGathered

# --- Configuration & Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("interface_component")

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
STORE_API_URL = "http://localhost:8001/files"
PROXY_WEBSITE_URL = "http://mock-proxy.local/api/receive-reply"

# --- FastStream Router Setup ---
router = RabbitRouter(RABBITMQ_URL)

# --- Scheduler Setup ---
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
    # FIX: Only bind the correlation_id. Leave the event for the actual log call.
    log = logger.bind(correlation_id=correlation_id)
    log.info("autonomous_scrape_started")

    heavy_payload = b"<html>...lots of scraped data...</html>"
    source_url = "https://example.com/news"

    try:
        # Mocking the Store response for now:
        uri = f"http://store:8001/files/mock-{uuid.uuid4().hex[:8]}.html"

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
            payload = {"user_id": action.user_id, "reply": action.payload}
            log.info("pushed_reply_to_proxy", payload=payload)
        except Exception as e:
            log.error("proxy_push_failed", payload={"error": str(e)})


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages the startup and shutdown of the Broker and Scheduler."""
    async with router.lifespan_context(app):
        scheduler.add_job(autonomous_scraping_job, 'interval', minutes=10)
        scheduler.start()

        # FIX: Just pass the event string positionally
        logger.info("interface_startup_complete")

        yield

        scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="Ana Interface Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "jobs_scheduled": len(scheduler.get_jobs())
    }
