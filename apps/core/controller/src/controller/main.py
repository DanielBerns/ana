import os
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import (
    ContextRequested, ContextProvided, CommandIssued,
    TaskCompleted, ActionRequired, PerceptionGathered, UserPromptReceived
)
from shared.logger import setup_logger
from .domain.rules import SymbolicRuleEngine

logger = setup_logger("controller")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/ana_v2")
adapter = RabbitMQAdapter(RABBITMQ_URL)

rule_engine = SymbolicRuleEngine()

@adapter.subscribe(queue_name="controller.context_responses", routing_key="context_responses")
async def on_context_provided(event: ContextProvided):
    # Find the most recent user message from the history provided by Memory
    latest_user_msg = next((msg["content"] for msg in reversed(event.history) if msg["role"] == "user"), "")

    cmd = CommandIssued(
        correlation_id=event.correlation_id,
        instruction="evaluate_user_intent",
        user_id=event.user_id,
        context_data={"raw_text": latest_user_msg, "history": event.history}
    )
    await adapter.publish(cmd, routing_key="commands")
    logger.info("context_evaluated_issuing_command")

@adapter.subscribe(queue_name="controller.perceptions", routing_key="perceptions")
async def on_perception_gathered(event: PerceptionGathered):
    """When new data is perceived, command the Actor to extract its symbolic facts."""
    logger.info("evaluating_new_perception", uri=event.uri)

    cmd = CommandIssued(
        correlation_id=event.correlation_id,
        instruction="extract_facts_from_perception",
        context_data={"uri": event.uri}
    )
    await adapter.publish(cmd, routing_key="commands")

@adapter.subscribe(queue_name="controller.task_evaluations", routing_key="task_completed")
async def on_task_completed(event: TaskCompleted):
    """Listens for completed tasks from the Actor and applies symbolic reasoning."""
    if event.task_name == "evaluate_user_intent" and event.status == "success":
        parts = event.result_summary.split("|")
        if len(parts) != 2:
            return

        intent = parts[0]
        confidence = float(parts[1])

        logger.info("applying_symbolic_rules", intent=intent, confidence=confidence)
        decisions = rule_engine.evaluate_intent(intent, confidence)

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
                    instruction=decision["instruction"],
                    context_data=decision.get("context_data", {})
                )
                await adapter.publish(cmd, routing_key="commands")
                logger.info("command_issued", command=decision["instruction"])

    elif event.task_name == "extract_facts" and event.status == "success":
        # Parse the extracted facts
        parts = event.result_summary.split("|")
        keywords = parts[0].split(":")[1]
        uri = parts[1].split(":")[1]

        logger.info("evaluating_extracted_facts", uri=uri, keywords=keywords)

        action = ActionRequired(
            correlation_id=event.correlation_id,
            action_type="reply_to_chat",
            payload=f"Analysis complete for {uri}. Key symbolic entities extracted: [{keywords}]"
        )
        await adapter.publish(action, routing_key="actions")

@adapter.subscribe(queue_name="controller.prompts", routing_key="user_prompts")
async def on_user_prompt(event: UserPromptReceived):
    """Intercepts raw human input and requests historical context from Memory."""
    logger.info("prompt_received_requesting_context")

    req = ContextRequested(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        query_reference=event.text,
        reply_to_topic="context_responses"
    )
    await adapter.publish(req, routing_key="context_requests")

app = FastStream(adapter.broker)
