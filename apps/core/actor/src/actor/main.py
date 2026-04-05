import os
from faststream import FastStream
import httpx

from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import CommandIssued, ActionRequired, TaskCompleted
from shared.logger import setup_logger
from .domain.classifier import IntentClassifier

from .domain.extractor import FactExtractor

logger = setup_logger("actor")
STORE_URL = os.getenv("STORE_URL", "http://edge-store:8002")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)
adapter = RabbitMQAdapter(RABBITMQ_URL)
classifier = IntentClassifier()
extractor = FactExtractor()

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
    elif event.instruction == "extract_facts_from_perception":
        uri = event.context_data.get("uri")
        logger.info("fetching_blob_for_extraction", uri=uri)

        try:
            # 1. Fetch the physical data artifact from the Edge Store
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{STORE_URL}/blobs/{uri}")
                html_content = resp.json().get("content", "")

            # 2. Process the text and extract symbolic facts
            clean_text = extractor.clean_html(html_content)
            keywords = extractor.extract_keywords(clean_text)

            logger.info("facts_extracted", keywords=keywords)

            # 3. Publish the extracted facts back to the Controller
            summary = f"extracted_keywords:{','.join(keywords)}|uri:{uri}"
            task_log = TaskCompleted(
                correlation_id=event.correlation_id,
                task_name="extract_facts",
                status="success",
                result_summary=summary
            )
            await adapter.publish(task_log, routing_key="task_completed")

        except Exception as e:
            logger.error("fact_extraction_failed", error=str(e))

app = FastStream(adapter.broker)
