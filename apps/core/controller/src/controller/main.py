import os
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import (
    ContextRequested, ContextProvided, CommandIssued,
    TaskCompleted, PerceptionGathered, UserPromptReceived
)
from shared.logger import setup_logger
from .domain.rules import SymbolicRuleEngine
from .domain.decisions import ActionDecision, CommandDecision

# Import the new infrastructure components
from .infrastructure.publishing import (
    DecisionPublisherRegistry,
    ActionPublisherStrategy,
    CommandPublisherStrategy
)

logger = setup_logger("controller")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)
adapter = RabbitMQAdapter(RABBITMQ_URL)

rule_engine = SymbolicRuleEngine()

# Initialize and map the Registry
publisher_registry = DecisionPublisherRegistry()
publisher_registry.register(ActionDecision, ActionPublisherStrategy())
publisher_registry.register(CommandDecision, CommandPublisherStrategy())



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

@adapter.subscribe(queue_name="controller.task_evaluations", routing_key="task_completed")
async def on_task_completed(event: TaskCompleted):
    """Listens for completed tasks from the Actor and delegates to the domain engine."""
    try:
        # 1. Strict Hexagonal Architecture: The engine now returns explicit DomainDecision models
        decisions = rule_engine.process_task_event(
            task_name=event.task_name,
            status=event.status,
            result_summary=event.result_summary
        )

        # 2. The adapter delegates entirely to the Registry. No OCP violations. No if/elif chains.
        for decision in decisions:
            await publisher_registry.publish(decision, adapter, event.correlation_id)
            logger.info("decision_published", decision_type=type(decision).__name__)

    except ValueError as e:
        logger.error("task_evaluation_domain_error", error=str(e), event_id=event.correlation_id)
    except NotImplementedError as e:
        # Catch unregistered strategies
        logger.error("task_evaluation_registry_error", error=str(e), event_id=event.correlation_id)
    except Exception as e:
        logger.exception("task_evaluation_unexpected_failure", error=str(e), event_id=event.correlation_id)

app = FastStream(adapter.broker)
