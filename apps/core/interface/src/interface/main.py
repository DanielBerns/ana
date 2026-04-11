import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import UserPromptReceived, PerceptionGathered, ActionRequired, CommandIssued
from shared.logger import setup_logger
from .infrastructure.clients import EdgeClient

import os

RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)
adapter = RabbitMQAdapter(RABBITMQ_URL)

logger = setup_logger("interface")

# URLs pointing to the Edge APIs we built in Phase 2
edge_client = EdgeClient(
    scraper_url=os.getenv("SCRAPER_URL", "http://localhost:8001"),
    store_url=os.getenv("STORE_URL", "http://localhost:8002")
)
scheduler = AsyncIOScheduler()


# --- FastStream Consumers (Outbound to Internet) ---
@adapter.subscribe(queue_name="interface.actions", routing_key="actions")
async def on_action_required(event: ActionRequired):
    """Listens for the core system deciding to reply to a human user."""
    if event.action_type == "reply_to_chat":
        logger.info("pushing_reply_to_proxy", user_id=event.user_id, reply=event.payload)
        # Domain Logic: HTTP POST to the external Proxy Website goes here

@adapter.subscribe(queue_name="interface.commands", routing_key="commands")
async def on_command(event: CommandIssued):
    """Listens for system commands that require interacting with the outside world."""

    if event.instruction == "execute_edge_scrape":
        # In the future, the Controller will pass the extracted URL in the context_data
        target_url = "https://example.com/news"
        logger.info("executing_edge_scrape_command", url=target_url)

        try:
            # 1. Ask Edge Scraper to get the data synchronously
            scrape_data = await edge_client.scrape(target_url)

            # 2. Ask Edge Store to save the heavy payload
            store_data = await edge_client.store_blob(scrape_data["content"])
            uri = store_data["uri"]

            # 3. Publish lightweight Perception event to the Core Event Broker
            perception = PerceptionGathered(
                correlation_id=event.correlation_id,
                source_url=target_url,
                uri=uri
            )
            await adapter.publish(perception, routing_key="perceptions")
            logger.info("perception_published_from_command", uri=uri)

            # 4. Tell the user the task is complete
            action = ActionRequired(
                correlation_id=event.correlation_id,
                action_type="reply_to_chat",
                user_id=event.user_id,
                payload=f"Scraping completed successfully. Data securely archived at URI: {uri}."
            )
            await adapter.publish(action, routing_key="actions")

        except Exception as e:
            logger.error("edge_scrape_command_failed", error=str(e))

            # Notify the user of the failure
            error_action = ActionRequired(
                correlation_id=event.correlation_id,
                action_type="reply_to_chat",
                user_id=event.user_id,
                payload="Failed to execute the scrape command. The Edge API may be unreachable."
            )
            await adapter.publish(error_action, routing_key="actions")

# --- Autonomous Scraping Flow (The "Claim Check" Pattern) ---
async def scheduled_scraping_task():
    """Runs on a cron schedule to gather internet data and feed it to the system."""
    target_url = "https://example.com/news"
    correlation_id = str(uuid.uuid4())
    logger.info("scheduled_scraping_started", url=target_url, correlation_id=correlation_id)

    try:
        # 1. Ask Edge Scraper to get the data synchronously
        scrape_data = await edge_client.scrape(target_url)

        # 2. Ask Edge Store to save the heavy payload
        store_data = await edge_client.store_blob(scrape_data["content"])
        uri = store_data["uri"]

        # 3. Publish lightweight Perception event to the Core Event Broker
        event = PerceptionGathered(
            correlation_id=correlation_id,
            source_url=target_url,
            uri=uri
        )
        await adapter.publish(event, routing_key="perceptions")
        logger.info("perception_published", uri=uri)

    except Exception as e:
        logger.error("scraping_task_failed", error=str(e))


# --- FastAPI Application (Inbound from Internet) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Graceful startup: Connect broker and start scheduler
    await adapter.broker.connect()

    # Schedule the autonomous task to run every 15 minutes
    scheduler.add_job(scheduled_scraping_task, 'interval', minutes=15)
    scheduler.start()

    yield

    # Graceful shutdown
    scheduler.shutdown()
    await adapter.broker.disconnect()

app = FastAPI(title="Ana Core: Interface Gateway", lifespan=lifespan)

class ProxyChatPayload(BaseModel):
    user_id: str
    message: str

@app.post("/webhook/chat")
async def receive_chat(payload: ProxyChatPayload):
    """Receives chat messages from the external authentication proxy."""
    correlation_id = str(uuid.uuid4())

    event = UserPromptReceived(
        correlation_id=correlation_id,
        user_id=payload.user_id,
        text=payload.message
    )

    # Push immediately to the core event bus
    await adapter.publish(event, routing_key="user_prompts")
    logger.info("user_prompt_published", user_id=payload.user_id)

    return {"status": "accepted", "correlation_id": correlation_id}
