import asyncio
from typing import Annotated
import structlog

from faststream import Context
from faststream.rabbit import RabbitRouter, RabbitQueue
from faststream.exceptions import RejectMessage

from ana.adapters.faststream_bus import commands_exchange
from ana.domain.messages import (
    ExecuteIONodeCommand,
    ResourceCreatedEvent,
    IONodeFailureEvent,
    MessageHeader,
)
from ana.ports.interfaces import ResourceRepositoryPort, MessageBusPort
from ana.adapters.registry import GatewayRegistry

inbound_router = RabbitRouter()

inbound_queue = RabbitQueue(
    "ana.queue.inbound", routing_key="ana.commands.ionode.inbound.*"
)


logger = structlog.get_logger("ana.agents.inbound")


class ExpectedDomainException(Exception):
    pass


@inbound_router.subscriber(queue=inbound_queue, exchange=commands_exchange)
async def handle_inbound_command(
    command: ExecuteIONodeCommand,
    registry: Annotated[GatewayRegistry, Context("registry")],
    repository: Annotated[ResourceRepositoryPort, Context("repository")],
    bus: Annotated[MessageBusPort, Context("bus")],
):
    # 1. FIXED: Bind using target_node_name
    structlog.contextvars.bind_contextvars(target_node_name=command.target_node_name)

    logger.info("Received ExecuteIONodeCommand", actions_count=len(command.actions))

    try:
        target_node_name = command.target_node_name
        coroutines = []

        # 2. FIXED: Iterate over command.actions
        for an_action in command.actions:
            # 3. FIXED: Access Pydantic attributes via dot notation
            action_name = an_action.name
            action_parameters = an_action.parameters

            # 4. FIXED: Look up the callable by action_name, not the node name
            action = registry.table.get(action_name)
            if not action:
                raise ExpectedDomainException(
                    f"Unknown action requested: {action_name} for node {target_node_name}"
                )

            coroutines.append(action(action_parameters))

        logger.debug(
            "Executing inbound actions concurrently", target_node_name=target_node_name
        )
        results = await asyncio.gather(*coroutines)

        # 5. FIXED: Zip against command.actions
        for (raw_payload, mime_type), action_executed in zip(results, command.actions):
            metadata = {
                "source_node": command.target_node_name,
                "command_id": command.header.message_id,
                # 6. FIXED: Access Pydantic attribute
                "action_executed": action_executed.name,
                "mime_type": mime_type,
            }

            resource_uri = await repository.save(raw_payload, metadata)
            logger.info(
                "Resource saved successfully",
                resource_uri=resource_uri,
                mime_type=mime_type,
            )

            event = ResourceCreatedEvent(
                header=MessageHeader(
                    correlation_id=command.header.correlation_id,
                    source_component=command.target_node_name,
                ),
                resource_uri=resource_uri,
                mime_type=mime_type,
                metadata=metadata,
            )
            await bus.publish_event(routing_key="event.resource.created", event=event)
            logger.debug("Emitted ResourceCreatedEvent")

    except ExpectedDomainException as e:
        logger.warning("Expected domain failure encountered", error_reason=str(e))
        failure_event = IONodeFailureEvent(
            header=MessageHeader(
                correlation_id=command.header.correlation_id,
                source_component=command.target_node_name,
            ),
            node_id=command.target_node_name,
            error_reason=str(e),
        )
        await bus.publish_event(routing_key="event.ionode.failed", event=failure_event)

    except Exception as e:
        logger.error("Unexpected error, explicit NACK to DLX", exc_info=True)
        raise RejectMessage() from e
