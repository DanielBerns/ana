import os
from faststream import FastStream
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import ContextRequested, ContextProvided, TaskCompleted, UserPromptReceived, PerceptionGathered
from shared.logger import setup_logger

from .infrastructure.database import get_db_session, initialize_storage, close_storage
from .infrastructure.repository import MemoryRepository

logger = setup_logger("memory")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)
adapter = RabbitMQAdapter(RABBITMQ_URL)

@adapter.subscribe(queue_name="memory.prompts_log", routing_key="user_prompts")
async def handle_user_prompt_log(
    event: UserPromptReceived,
    session: AsyncSession = Depends(get_db_session)
):
    """Records incoming prompts into the ledger AND the Knowledge Graph."""
    repo = MemoryRepository(session)

    # 1. Log to the deterministic ledger
    await repo.log_event(
        correlation_id=event.correlation_id,
        event_type=event.event_type,
        payload={"user_id": event.user_id, "text": event.text}
    )

    # 2. Extract semantic knowledge into the Quad-Store
    graph_id = f"session:{event.user_id}"
    await repo.ensure_graph_exists(graph_id, f"Interaction context for {event.user_id}")

    await repo.ensure_entity_exists(
        entity_id=event.user_id,
        entity_type="user",
        name=event.user_id
    )

    await repo.assert_quad(
        subject_id=event.user_id,
        predicate="stated",
        object_literal_value=event.text,
        graph_id=graph_id,
        correlation_id=event.correlation_id,
        confidence=1.0
    )

    logger.info("archived_user_prompt_as_quad", user_id=event.user_id, graph=graph_id)

@adapter.subscribe(queue_name="memory.context_requests", routing_key="context_requests")
async def handle_context_request(
    event: ContextRequested,
    session: AsyncSession = Depends(get_db_session)
):
    logger.info("fetching_context_for_request", query=event.query_reference)

    repo = MemoryRepository(session)
    recent_logs = await repo.get_recent_history(limit=20)

    history = []
    for log in recent_logs:
        if "text" in log:
            role = "user" if "user_id" in log else "system"
            history.append({"role": role, "content": log["text"]})

    if not history:
        history = [{"role": "system", "content": "No prior context available."}]

    response_event = ContextProvided(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        history=history[-5:],
        trigger_event={"query": event.query_reference}
    )

    await adapter.publish(response_event, routing_key=event.reply_to_topic)
    logger.info("context_provided_and_published", history_length=len(history))

@adapter.subscribe(queue_name="memory.task_logs", routing_key="task_completed")
async def handle_task_completed(
    event: TaskCompleted,
    session: AsyncSession = Depends(get_db_session)
):
    """Archives the result of an Actor's execution."""
    repo = MemoryRepository(session)
    await repo.log_event(
        correlation_id=event.correlation_id,
        event_type=event.event_type,
        payload={"task": event.task_name, "status": event.status, "summary": event.result_summary}
    )
    logger.info("archived_task_record", task=event.task_name, status=event.status)

@adapter.subscribe(queue_name="memory.perceptions", routing_key="perceptions")
async def handle_perception_gathered(
    event: PerceptionGathered,
    session: AsyncSession = Depends(get_db_session)
):
    """Archives the physical location of perceived data into the Knowledge Graph."""
    repo = MemoryRepository(session)

    # 1. Log to the deterministic ledger
    await repo.log_event(
        correlation_id=event.correlation_id,
        event_type=event.event_type,
        payload={"source_url": event.source_url, "uri": event.uri}
    )

    # 2. Extract semantic knowledge into the Quad-Store
    graph_id = "system:perceptions"
    await repo.ensure_graph_exists(graph_id, "System-wide data perception and provenance tracking")

    await repo.ensure_entity_exists(
        entity_id=event.uri,
        entity_type="data_artifact",
        name=f"Artifact: {event.uri}"
    )

    await repo.assert_quad(
        subject_id=event.uri,
        predicate="originates_from",
        object_literal_value=event.source_url,
        graph_id=graph_id,
        correlation_id=event.correlation_id,
        confidence=1.0
    )

    logger.info("archived_perception_as_quad", artifact=event.uri, source=event.source_url, graph=graph_id)

app = FastStream(adapter.broker)

@app.on_startup
async def on_startup():
    """Initializes external resources before consuming events."""
    await initialize_storage()

@app.on_shutdown
async def on_shutdown():
    """Cleanly closes external resources."""
    await close_storage()
