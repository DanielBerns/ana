from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import (
    PerceptionGathered, UserPromptReceived, ContextRequested,
    ContextProvided, CommandIssued
)
from shared.logger import setup_logger
import os

from shared.events import (
    PerceptionGathered, UserPromptReceived, ContextRequested,
    ContextProvided, CommandIssued, TaskCompleted, ActionRequired
)
from .domain.rules import SymbolicRuleEngine

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
adapter = RabbitMQAdapter(RABBITMQ_URL)

logger = setup_logger("controller")

rule_engine = SymbolicRuleEngine()

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
    # Find the most recent user message from the history provided by Memory
    latest_user_msg = next((msg["content"] for msg in reversed(event.history) if msg["role"] == "user"), "")

    cmd = CommandIssued(
        correlation_id=event.correlation_id,
        instruction="evaluate_user_intent",
        user_id=event.user_id,
        context_data={"raw_text": latest_user_msg, "history": event.history}
    )
    await adapter.publish(cmd, routing_key="commands")

@adapter.subscribe(queue_name="controller.task_evaluations", routing_key="task_completed")
async def on_task_completed(event: TaskCompleted):
    """Listens for completed perceptions and applies symbolic reasoning."""
    if event.task_name == "evaluate_user_intent" and event.status == "success":
        # Parse the statistical fact provided by the Actor
        parts = event.result_summary.split("|")
        if len(parts) != 2:
            return

        intent = parts[0]
        confidence = float(parts[1])

        logger.info("applying_symbolic_rules", intent=intent, confidence=confidence)

        # Consult the Neurosymbolic Rule Engine
        decisions = rule_engine.evaluate_intent(intent, confidence)

        # Execute the deterministic decisions
        for decision in decisions:
            if decision["type"] == "action":
                action = ActionRequired(
                    correlation_id=event.correlation_id,
                    action_type=decision["action_type"],
                    payload=decision["payload"]
                )
                await adapter.publish(action, routing_key="actions")
                logger.info("action_issued", action=decision["action_type"])

            elif decision["type"] == "command":
                cmd = CommandIssued(
                    correlation_id=event.correlation_id,
                    instruction=decision["instruction"]
                )
                await adapter.publish(cmd, routing_key="commands")
                logger.info("command_issued", command=decision["instruction"])


app = FastStream(adapter.broker)
