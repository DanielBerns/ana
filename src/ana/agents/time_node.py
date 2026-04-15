# ana/agents/time_node.py
import yaml
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ana.domain.messages import ExecuteIONodeCommand, MessageHeader
from ana.ports.interfaces import MessageBusPort

# Initialize the asyncio-compatible scheduler
scheduler_app = AsyncIOScheduler()

def load_actions_from_config(bus: MessageBusPort, config_path: str):
    """Dynamically creates APScheduler actions based on the YAML configuration."""
    path = Path(config_path)
    if not path.exists():
        return

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    for action_def in config.get("actions", []):
        action_name = action_def.get("name", "error")
        action_cron_expression = action_def.get("cron", '0 0 * * *')
        action_target_node_name: action_def.get("target_node_name", "ErrorHandler")
        action_parameters = action_def.get("parameters", {})
        # Define the async action
        async def schedule_command_publication(name=action_name):
            this_command = ExecuteIONodeCommand(
                header=MessageHeader(
                    correlation_id=f"time_{action_name}",
                    source_component="TimeNode"
                ),
                name=action_name,
                target_node_id=action_target_node_id,
                parameters=action_parameters
            )
            await bus.publish_command(routing_key="command.ionode.inbound.fetch", command=this_command)

        # Add the job to the scheduler using standard crontab parsing
        scheduler_app.add_job(
            schedule_command_publication,
            CronTrigger.from_crontab(action_cron_expression),
            id=action_name,
            replace_existing=True
        )
