import os
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import ContextRequested, ContextProvided, TaskCompleted, UserPromptReceived
from shared.logger import setup_logger

from .infrastructure.database import AsyncSessionLocal
from .infrastructure.repository import MemoryRepository

logger = setup_logger("memory")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/ana_v2")
adapter = RabbitMQAdapter(RABBITMQ_URL)

@adapter.subscribe(queue_name="memory.prompts_log", routing_key="user_prompts")
async def handle_user_prompt_log(event: UserPromptReceived):
    """Silently records incoming user prompts into the deterministic ledger."""
    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)
        await repo.log_event(
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            payload={"user_id": event.user_id, "text": event.text}
        )
    logger.info("archived_user_prompt", user_id=event.user_id)

@adapter.subscribe(queue_name="memory.context_requests", routing_key="context_requests")
async def handle_context_request(event: ContextRequested):
    logger.info("fetching_context_for_request", query=event.query_reference)

    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)
        recent_logs = await repo.get_recent_history()

    # Format the DB logs into a standard history payload
    history = [{"role": "user" if "user_id" in log else "system", "content": log.get("text", str(log))} for log in recent_logs]

    if not history:
        history = [{"role": "system", "content": "No prior context available."}]

    response_event = ContextProvided(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        history=history,
        trigger_event={"query": event.query_reference}
    )

    await adapter.publish(response_event, routing_key=event.reply_to_topic)
    logger.info("context_provided_and_published", history_length=len(history))

@adapter.subscribe(queue_name="memory.task_logs", routing_key="task_completed")
async def handle_task_completed(event: TaskCompleted):
    """Archives the result of an Actor's execution."""
    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)
        await repo.log_event(
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            payload={"task": event.task_name, "status": event.status, "summary": event.result_summary}
        )
    logger.info("archived_task_record", task=event.task_name, status=event.status)

app = FastStream(adapter.broker)
