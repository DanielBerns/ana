# ana/agents/inbound_node.py
import asyncio
from typing import Annotated

from faststream import Context
from faststream.rabbit import RabbitRouter, RabbitQueue
from faststream.exceptions import RejectMessage

from ana.adapters.faststream_bus import commands_exchange
from ana.domain.messages import (
    ExecuteIONodeCommand,
    ResourceCreatedEvent,
    IONodeFailureEvent,
    MessageHeader
)
from ana.ports.interfaces import ResourceRepositoryPort, MessageBusPort
from ana.adapters.registry import GatewayRegistry

inbound_router = RabbitRouter()
inbound_queue = RabbitQueue("ana.queue.inbound", routing_key="command.ionode.inbound.*")

class ExpectedDomainException(Exception):
    """An expected failure (e.g., a 404 from an external API)."""
    pass

@inbound_router.subscriber(queue=inbound_queue, exchange=commands_exchange)
async def handle_inbound_command(
    command: ExecuteIONodeCommand,
    registry: Annotated[GatewayRegistry, Context("registry")],
    repository: Annotated[ResourceRepositoryPort, Context("repository")],
    bus: Annotated[MessageBusPort, Context("bus")]
):
    """Executes multiple registered actions in parallel, saves the payloads, and emits events."""
    try:
        actions = command.actions
        if not actions:
            return  # No actions defined, exit gracefully

        target_node_name = command.target_node_name

        # 1. Prepare and execute actions concurrently
        coroutines = []
        for an_action in actions:
            action_name = an_action.get("name", "")
            action_cron = an_action.get("cron", "0 0 * * *")
            action_parameters = an_action.get("parameters", {})

            action = registry.table.get(target_node_name)
            if not action:
                raise ExpectedDomainException(f"Unknown target_node_name requested: {target_node_name} - {action_name}")

            coroutines.append(action(action_parameters))

        # Run all prepared HTTP actions in parallel
        results = await asyncio.gather(*coroutines)

        # 2. Process results, save to repository, and emit events
        for (raw_payload, mime_type), action_executed in zip(results, actions):
            metadata = {
                "source_node": command.target_node_name,
                "command_id": command.header.message_id,
                "action_executed": action_executed.get("name")
                "mime_type": mime_type
            }

            # Save to local storage / Gel database
            resource_uri = await repository.save(raw_payload, metadata)

            # Emit the ResourceCreatedEvent
            event = ResourceCreatedEvent(
                header=MessageHeader(
                    correlation_id=command.header.correlation_id,
                    source_component=command.target_node_id
                ),
                resource_uri=resource_uri,
                mime_type=mime_type,
                metadata=metadata
            )
            await bus.publish_event(routing_key="event.resource.created", event=event)

    except ExpectedDomainException as e:
        # Expected failure: Emit IONodeFailureEvent and halt.
        failure_event = IONodeFailureEvent(
            header=MessageHeader(correlation_id=command.header.correlation_id, source_component=command.target_node_id),
            node_id=command.target_node_id,
            error_reason=str(e)
        )
        await bus.publish_event(routing_key="event.ionode.failed", event=failure_event)

    except Exception as e:
        # UNEXPECTED STATE: Explicit NACK to DLX
        raise RejectMessage() from e
