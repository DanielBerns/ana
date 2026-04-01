from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import (
    PerceptionGathered, UserPromptReceived, ContextRequested,
    ContextProvided, CommandIssued
)
from shared.logger import setup_logger

logger = setup_logger("controller")
adapter = RabbitMQAdapter("amqp://guest:guest@localhost:5672/")

@adapter.subscribe(queue_name="controller.perceptions", routing_key="perceptions")
async def on_perception(event: PerceptionGathered):
    logger.info("perception_received_requesting_context")
    req = ContextRequested(
        correlation_id=event.correlation_id,
        query_reference=event.uri,
        reply_to_topic="controller.context_responses"
    )
    await adapter.publish(req, routing_key="context_requests")

@adapter.subscribe(queue_name="controller.prompts", routing_key="user_prompts")
async def on_user_prompt(event: UserPromptReceived):
    logger.info("prompt_received_requesting_context")
    req = ContextRequested(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        query_reference=event.text,
        reply_to_topic="controller.context_responses"
    )
    await adapter.publish(req, routing_key="context_requests")

@adapter.subscribe(queue_name="controller.context_responses", routing_key="controller.context_responses")
async def on_context_provided(event: ContextProvided):
    logger.info("context_evaluated_issuing_command")

    # Domain Logic: Rule Engine evaluation goes here.
    # If the context was triggered by a chat, we command the actor to reply.
    cmd = CommandIssued(
        correlation_id=event.correlation_id,
        instruction="generate_chat_reply",
        user_id=event.user_id,
        context_data={"history": event.history}
    )
    await adapter.publish(cmd, routing_key="commands")

app = FastStream(adapter.broker)
