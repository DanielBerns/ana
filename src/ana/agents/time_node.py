import uuid
import yaml
from pathlib import Path

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Update imports to include your new config models
from ana.domain.messages import (
    ExecuteIONodeCommand,
    MessageHeader,
    SchedulerConfig,
    ScheduledAction,
)
from ana.ports.interfaces import MessageBusPort

logger = structlog.get_logger("ana.agents.time_node")
scheduler_app = AsyncIOScheduler()


def load_actions_from_config(bus: MessageBusPort, config_file: Path):
    """Dynamically creates APScheduler actions based on the YAML configuration."""

    logger.info(
        "Loading scheduled actions from configuration", config_path=str(config_file)
    )

    if not config_file.exists():
        logger.warning(
            "Configuration file not found, skipping scheduled actions.",
            config_path=str(config_file),
        )
        return

    # 1. Parse and strictly validate the configuration using Pydantic
    with config_file.open("r") as f:
        raw_data = yaml.safe_load(f)

    config = SchedulerConfig(**raw_data)

    # 2. Iterate through nodes and their individual actions
    for node in config.nodes:
        target_name = node.target_node_name

        for action in node.actions:
            # 3. Define the async job, binding loop variables as default arguments
            # to prevent Python's late-binding closure behavior in loops
            async def schedule_command_publication(
                current_target: str = target_name,
                current_action: ScheduledAction = action,
            ):
                structlog.contextvars.clear_contextvars()
                run_id = f"time_{current_action.name}_{uuid.uuid4().hex[:8]}"

                structlog.contextvars.bind_contextvars(
                    correlation_id=run_id,
                    source="TimeNode",
                    action_name=current_action.name,
                )

                logger.info(
                    "Executing scheduled job",
                    cron=current_action.cron,
                    target_node_name=current_target,
                )

                # 4. Generate the ExecuteIONodeCommand
                # We wrap the current_action in a list to satisfy the List[ScheduledAction] schema
                this_command = ExecuteIONodeCommand(
                    header=MessageHeader(
                        correlation_id=run_id, source_component="TimeNode"
                    ),
                    target_node_name=current_target,
                    actions=[current_action],
                )

                await bus.publish_command(
                    routing_key="command.ionode.inbound.fetch", command=this_command
                )
                logger.debug("Scheduled command published successfully to message bus")

            # 5. Add the specific action to the scheduler
            # Ensure the job ID is unique by combining node and action name
            scheduler_app.add_job(
                schedule_command_publication,
                CronTrigger.from_crontab(action.cron),
                id=f"{target_name}_{action.name}",
                replace_existing=True,
            )
            logger.debug(
                "Registered scheduled job",
                target=target_name,
                action=action.name,
                cron=action.cron,
            )
