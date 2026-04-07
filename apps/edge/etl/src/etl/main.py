import os
import httpx
from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import CommandIssued, PerceptionGathered, ActionRequired, TaskCompleted
from shared.logger import setup_logger
from .domain.pipeline import ETLPipeline

logger = setup_logger("edge_etl")

RABBITMQ_URL = os.getenv("RABBITMQ_URL", RABBITMQ_URL_DEFAULT)
STORE_URL = os.getenv("STORE_URL", "http://edge-store:8002")
adapter = RabbitMQAdapter(RABBITMQ_URL)

pipeline = ETLPipeline()

@adapter.subscribe(queue_name="etl.commands", routing_key="commands")
async def on_command(event: CommandIssued):
    if event.instruction == "execute_etl_pipeline":
        config = event.context_data.get("pipeline_config", {})
        source_url = config.get("source", "unknown")
        logger.info("executing_etl_pipeline", source=source_url, config=config)

        try:
            # 1. Run the dynamic ETL Pipeline
            formatted_data = await pipeline.execute(config)

            # 2. Upload to Edge Store (Using the new Document endpoint)
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{STORE_URL}/api/v1/documents",
                    json={"content": formatted_data}
                )
                resp.raise_for_status()
                uri = resp.json()["uri"]

            # 3. Publish Perception
            perception = PerceptionGathered(
                correlation_id=event.correlation_id,
                source_url=source_url,
                uri=uri
            )
            await adapter.publish(perception, routing_key="perceptions")
            logger.info("etl_pipeline_success", uri=uri)

            # 4. Notify completion (Passing structured context, not a string)
            task = TaskCompleted(
                correlation_id=event.correlation_id,
                task_name="execute_etl",
                status="success",
                result_summary={"source_url": source_url, "artifact_uri": uri} # Structure the summary
            )
            await adapter.publish(task, routing_key="task_completed")

        except Exception as e:
            logger.error("etl_pipeline_failed", error=str(e))

            # FIX: Ensure Memory logs the failed task execution
            task_failed = TaskCompleted(
                correlation_id=event.correlation_id,
                task_name="execute_etl",
                status="failure",
                result_summary={"source_url": source_url, "error": str(e)}
            )
            await adapter.publish(task_failed, routing_key="task_completed")

            # FIX: Request operator intervention
            action = ActionRequired(
                correlation_id=event.correlation_id,
                action_type="reply_to_chat",
                user_id=event.user_id,
                payload=f"ETL Pipeline failed for source '{source_url}'. Error: {str(e)}"
            )
            await adapter.publish(action, routing_key="actions")

app = FastStream(adapter.broker)
