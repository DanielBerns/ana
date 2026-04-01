from faststream import FastStream
from shared.infrastructure import RabbitMQAdapter
from shared.events import CommandIssued, ActionRequired, TaskCompleted
from shared.logger import setup_logger

logger = setup_logger("actor")
adapter = RabbitMQAdapter("amqp://guest:guest@localhost:5672/")

@adapter.subscribe(queue_name="actor.commands", routing_key="commands")
async def on_command(event: CommandIssued):
    logger.info("executing_command", instruction=event.instruction)

    if event.instruction == "generate_chat_reply":
        # Domain Logic: Call LLM Provider here.
        mock_reply = "This is a generated response from Ana's isolated core."

        # 1. Ask the Interface to send the reply to the user
        action = ActionRequired(
            correlation_id=event.correlation_id,
            action_type="reply_to_chat",
            user_id=event.user_id,
            payload=mock_reply
        )
        await adapter.publish(action, routing_key="actions")

        # 2. Tell Memory the task is done so it can be logged
        task_log = TaskCompleted(
            correlation_id=event.correlation_id,
            task_name="generate_chat_reply",
            status="success",
            result_summary="Successfully generated and pushed reply to interface."
        )
        await adapter.publish(task_log, routing_key="task_completed")

app = FastStream(adapter.broker)
