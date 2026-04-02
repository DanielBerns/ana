import os
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import CommandIssued, ActionRequired, TaskCompleted
from shared.logger import setup_logger
from .domain.classifier import IntentClassifier

logger = setup_logger("actor")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/ana_v2")
adapter = RabbitMQAdapter(RABBITMQ_URL)

# Initialize the statistical perception engine
classifier = IntentClassifier()

@adapter.subscribe(queue_name="actor.commands", routing_key="commands")
async def on_command(event: CommandIssued):
    logger.info("executing_command", instruction=event.instruction)

    if event.instruction == "evaluate_user_intent":
        # 1. Extract the raw text
        raw_text = event.context_data.get("raw_text", "")

        # 2. Perform statistical classification
        result = classifier.classify(raw_text)
        predicted_intent = result["intent"]
        confidence = result["confidence"]

        logger.info("text_classified", raw_text=raw_text, intent=predicted_intent, confidence=confidence)

        # 3. Archive the perception as a structured fact (No direct replying!)
        # We pass the exact statistical data in the result_summary so the Controller can read it.
        task_log = TaskCompleted(
            correlation_id=event.correlation_id,
            task_name="evaluate_user_intent",
            status="success",
            result_summary=f"{predicted_intent}|{confidence}"
        )
        await adapter.publish(task_log, routing_key="task_completed")

app = FastStream(adapter.broker)
