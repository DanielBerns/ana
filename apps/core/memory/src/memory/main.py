import asyncio
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import ContextRequested, ContextProvided, TaskCompleted
from shared.logger import setup_logger

logger = setup_logger("memory")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
adapter = RabbitMQAdapter(RABBITMQ_URL)

@adapter.subscribe(queue_name="memory.context_requests", routing_key="context_requests")
async def handle_context_request(event: ContextRequested):
    logger.info("fetching_context_for_request", query=event.query_reference)

    # Domain Logic: Query PostgreSQL here.
    # For now, we mock the retrieved history.
    mock_history = [{"role": "system", "content": "You are Ana."}]

    response_event = ContextProvided(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        history=mock_history,
        trigger_event={"query": event.query_reference}
    )

    # Publish back to the topic requested by the Controller
    await adapter.publish(response_event, routing_key=event.reply_to_topic)
    logger.info("context_provided_and_published")

@adapter.subscribe(queue_name="memory.task_logs", routing_key="task_completed")
async def handle_task_completed(event: TaskCompleted):
    # Domain Logic: Insert into PostgreSQL audit table
    logger.info("archiving_task_record", task=event.task_name, status=event.status)

app = FastStream(adapter.broker)
