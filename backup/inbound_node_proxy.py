import json
from faststream.rabbit import RabbitRouter
from faststream import Logger

from ana.domain.messages import ExecuteIONodeCommand
from ana.ports.interfaces import MessageBusPort
from ana.adapters.registry import GatewayRegistry

router = RabbitRouter()


@router.subscriber("command.ionode.inbound.fetch")
async def handle_proxy_poll(
    command: ExecuteIONodeCommand,
    bus: MessageBusPort,
    registry: GatewayRegistry,
    logger: Logger,
):
    """
    Triggered by APScheduler via time_node.py.
    Executes the fetch, parses deterministically, and distributes tasks.
    """
    task_name = command.parameters.get("task_name")
    if task_name != "proxy_sync_poll":
        return  # Ignore other timer events

    logger.info("Executing proxy polling cycle...")

    try:
        # 1. Execute the HTTP action via the registry
        action_callable = registry.table.get("proxy_fetch_tasks")
        if not action_callable:
            logger.error("Action 'proxy_fetch_tasks' not found in registry.")
            return

        payload_bytes, mime_type = await action_callable({})

        # 2. Strict, deterministic parsing (No LLMs)
        raw_tasks = json.loads(payload_bytes.decode("utf-8"))

        if not raw_tasks:
            logger.info("No pending tasks found.")
            return

        # 3. Translate and distribute
        for raw_task in raw_tasks:
            # We map to the internal PendingTask dataclass we defined in Phase 2
            task_id = raw_task.get("id")

            # Publish individual events for internal workers to process asynchronously
            await bus.publish(
                "event.proxy.task.received",
                {
                    "task_id": task_id,
                    "command_type": raw_task.get("command_type"),
                    "parameters": raw_task.get("parameters", {}),
                },
                headers={"correlation_id": task_id},
            )
            logger.info(f"Published event.proxy.task.received for task {task_id}")

    except Exception as e:
        logger.error(f"Proxy polling cycle failed: {str(e)}")
