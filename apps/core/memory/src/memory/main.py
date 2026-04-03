import os
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import ContextRequested, ContextProvided, TaskCompleted, UserPromptReceived, PerceptionGathered
from shared.logger import setup_logger

from .infrastructure.database import AsyncSessionLocal
from .infrastructure.repository import MemoryRepository

logger = setup_logger("memory")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/ana_v2")
adapter = RabbitMQAdapter(RABBITMQ_URL)

@adapter.subscribe(queue_name="memory.prompts_log", routing_key="user_prompts")
async def handle_user_prompt_log(event: UserPromptReceived):
    """Records incoming prompts into the ledger AND the Knowledge Graph."""
    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)

        # 1. Log to the deterministic ledger (unchanged)
        await repo.log_event(
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            payload={"user_id": event.user_id, "text": event.text}
        )

        # 2. Extract semantic knowledge into the Quad-Store!
        # Define the 4th Dimension (The Context Graph)
        graph_id = f"session:{event.user_id}"
        await repo.ensure_graph_exists(graph_id, f"Interaction context for {event.user_id}")

        # Define the Subject Entity
        await repo.ensure_entity_exists(
            entity_id=event.user_id,
            entity_type="user",
            name=event.user_id
        )

        # Assert the 4-tuple (S: user, P: "stated", O: literal_text, G: session_graph)
        await repo.assert_quad(
            subject_id=event.user_id,
            predicate="stated",
            object_literal_value=event.text,
            graph_id=graph_id,
            correlation_id=event.correlation_id,
            confidence=1.0 # 100% confident because the user directly typed it
        )

    logger.info("archived_user_prompt_as_quad", user_id=event.user_id, graph=graph_id)

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

@adapter.subscribe(queue_name="memory.perceptions", routing_key="perceptions")
async def handle_perception_gathered(event: PerceptionGathered):
    """Archives the physical location of perceived data into the Knowledge Graph."""
    async with AsyncSessionLocal() as session:
        repo = MemoryRepository(session)

        # 1. Log to the deterministic ledger
        await repo.log_event(
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            payload={"source_url": event.source_url, "uri": event.uri}
        )

        # 2. Extract semantic knowledge into the Quad-Store!
        # Define the 4th Dimension (A systemic graph for tracking data provenance)
        graph_id = "system:perceptions"
        await repo.ensure_graph_exists(graph_id, "System-wide data perception and provenance tracking")

        # Define the Subject Entity (The physical artifact in the Edge Store)
        await repo.ensure_entity_exists(
            entity_id=event.uri,
            entity_type="data_artifact",
            name=f"Artifact: {event.uri}"
        )

        # Assert the 4-tuple (S: artifact_uri, P: "originates_from", O: source_url, G: perceptions_graph)
        await repo.assert_quad(
            subject_id=event.uri,
            predicate="originates_from",
            object_literal_value=event.source_url,
            graph_id=graph_id,
            correlation_id=event.correlation_id,
            confidence=1.0 # 100% confident because the system performed the scrape itself
        )

    logger.info("archived_perception_as_quad", artifact=event.uri, source=event.source_url, graph=graph_id)

app = FastStream(adapter.broker)
