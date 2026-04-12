# ana/agents/inbound_node.py
import asyncio
from typing import Annotated

from faststream import Context, Depends
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

# Define the router and the queue with our DLX configuration
inbound_router = RabbitRouter()
inbound_queue = RabbitQueue("ana.queue.inbound", routing_key="command.ionode.inbound.*")


class ExpectedDomainException(Exception):
    """An expected failure (e.g., a 404 from an external API)."""
    pass


@inbound_router.subscriber(queue=inbound_queue, exchange=commands_exchange)
async def handle_inbound_command(
    command: ExecuteIONodeCommand,
    # FastStream automatically injects these from the app context
    repository: Annotated[ResourceRepositoryPort, Context("repository")],
    bus: Annotated[MessageBusPort, Context("bus")]
):
    """Executes the fetch, saves the payload, and emits an event."""
    try:
        # 1. Simulate fetching data from an external source based on command parameters
        if command.parameters.get("simulate_fatal_error"):
            # Simulate a database crash or out-of-memory error
            raise RuntimeError("Unexpected fatal system state!")

        if command.parameters.get("simulate_api_down"):
            # Simulate an expected, handled domain failure
            raise ExpectedDomainException("External API returned 503 Unavailable.")

        # Simulate a successful fetch payload
        raw_payload = b'{"status": "success", "data": "Sample external data"}'
        mime_type = "application/json"

        # 2. Save to the Resource Repository
        metadata = {"source_node": command.target_node_id, "command_id": command.header.message_id}
        resource_uri = await repository.save(raw_payload, metadata)

        # 3. Emit the ResourceCreatedEvent
        event = ResourceCreatedEvent(
            header=MessageHeader(correlation_id=command.header.correlation_id, source_component=command.target_node_id),
            resource_uri=resource_uri,
            mime_type=mime_type,
            metadata=metadata
        )
        await bus.publish_event(routing_key="event.resource.created", event=event)

    except ExpectedDomainException as e:
        # Expected failure: Emit IONodeFailureEvent and halt.
        # The message is acknowledged normally so it leaves the queue.
        failure_event = IONodeFailureEvent(
            header=MessageHeader(correlation_id=command.header.correlation_id, source_component=command.target_node_id),
            node_id=command.target_node_id,
            error_reason=str(e)
        )
        await bus.publish_event(routing_key="event.ionode.failed", event=failure_event)

    except Exception as e:
        # UNEXPECTED STATE: Explicit NACK
        # FastStream's RejectMessage routes it to the Dead Letter Exchange
        raise RejectMessage() from e
