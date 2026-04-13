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
        tasks = command.parameters.get("tasks", [])
        if not tasks:
            return  # No tasks defined, exit gracefully

        # 1. Prepare and execute tasks concurrently
        coroutines = []
        for task in tasks:
            action_key = task.get("action_key", "")
            action_parameters = task.get("action_parameters", {})

            action = registry.table.get(action_key)
            if not action:
                raise ExpectedDomainException(f"Unknown action key requested: {action_key}")

            coroutines.append(action(action_parameters))

        # Run all prepared HTTP actions in parallel
        results = await asyncio.gather(*coroutines)

        # 2. Process results, save to repository, and emit events
        for (raw_payload, mime_type), task_def in zip(results, tasks):
            metadata = {
                "source_node": command.target_node_id,
                "command_id": command.header.message_id,
                "action_executed": task_def.get("action_key")
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
