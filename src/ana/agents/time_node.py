# ana/agents/time_node.py
import yaml
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ana.domain.messages import ExecuteIONodeCommand, MessageHeader
from ana.ports.interfaces import MessageBusPort

# Initialize the asyncio-compatible scheduler
scheduler_app = AsyncIOScheduler()

def load_tasks_from_config(bus: MessageBusPort, config_path: str = "config/scheduler.yml"):
    """Dynamically creates APScheduler tasks based on the YAML configuration."""
    path = Path(config_path)
    if not path.exists():
        return

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    for task_def in config.get("tasks", []):
        task_name = task_def["name"]
        cron_expr = task_def["cron"]

        # Define the async task
        async def dynamic_publish_task(name=task_name):
            command = ExecuteIONodeCommand(
                header=MessageHeader(
                    correlation_id=f"time_{name}",
                    source_component="TimeNode"
                ),
                target_node_id="inbound_api_fetcher",
                parameters={"task_name": name}
            )
            await bus.publish_command(routing_key="command.ionode.inbound.fetch", command=command)

        # Add the job to the scheduler using standard crontab parsing
        scheduler_app.add_job(
            dynamic_publish_task,
            CronTrigger.from_crontab(cron_expr),
            id=task_name,
            replace_existing=True
        )
