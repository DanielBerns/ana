import os
from faststream import FastStream

from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import CommandIssued, TaskCompleted
from shared.logger import setup_logger

from .domain.classifier import IntentClassifier
from .domain.extractor import FactExtractor

# Import our new application/infrastructure components
from .application.handlers import (
    CommandHandlerRegistry,
    EvaluateIntentHandler,
    ExtractFactsHandler
)

logger = setup_logger("actor")
STORE_URL = os.getenv("STORE_URL", "http://edge-store:8002")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)

adapter = RabbitMQAdapter(RABBITMQ_URL)

# Instantiate domain services
classifier = IntentClassifier()
extractor = FactExtractor()

# Initialize and map the Registry
command_registry = CommandHandlerRegistry()
command_registry.register("evaluate_user_intent", EvaluateIntentHandler(classifier))
command_registry.register("extract_facts_from_perception", ExtractFactsHandler(extractor, STORE_URL))


@adapter.subscribe(queue_name="actor.commands", routing_key="commands")
async def on_command(event: CommandIssued):
    logger.info("received_command", instruction=event.instruction)

    try:
        # 1. Delegate entirely to the registry. No if/elif blocks.
        task_log: TaskCompleted = await command_registry.handle(event)

        # 2. Publish the successful result back to the Controller
        await adapter.publish(task_log, routing_key="task_completed")
        logger.info("command_executed_successfully", instruction=event.instruction)

    except ValueError as e:
        # Instruction wasn't found in the registry
        logger.error("unsupported_command", error=str(e), correlation_id=event.correlation_id)

        # Publish a failure event so the Controller isn't left hanging
        failure_log = TaskCompleted(
            correlation_id=event.correlation_id,
            task_name=event.instruction,
            status="failure",
            result_summary={"error": str(e)}
        )
        await adapter.publish(failure_log, routing_key="task_completed")

    except Exception as e:
        # Catch unexpected handler failures (e.g., HTTP errors in ExtractFacts)
        logger.exception("command_execution_failed", error=str(e), correlation_id=event.correlation_id)

        failure_log = TaskCompleted(
            correlation_id=event.correlation_id,
            task_name=event.instruction,
            status="failure",
            result_summary={"error": "Internal handler failure"}
        )
        await adapter.publish(failure_log, routing_key="task_completed")


app = FastStream(adapter.broker)
