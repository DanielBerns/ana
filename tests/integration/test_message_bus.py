# tests/integration/test_message_bus.py
import json
import pytest
from faststream.rabbit import TestRabbitBroker, RabbitBroker, RabbitQueue

from ana.adapters.faststream_bus import FastStreamMessageBus, commands_exchange, events_exchange
from ana.domain.messages import ExecuteIONodeCommand, ResourceCreatedEvent, MessageHeader


@pytest.mark.asyncio
async def test_publish_command():
    broker = RabbitBroker()

    dummy_cmd_queue = RabbitQueue("dummy_cmd_queue", routing_key="command.ionode.inbound.fetch")

    @broker.subscriber(queue=dummy_cmd_queue, exchange=commands_exchange)
    async def dummy_handler(msg: ExecuteIONodeCommand):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        command = ExecuteIONodeCommand(
            header=MessageHeader(correlation_id="test-123", source_component="test"),
            target_node_id="node_1"
        )

        await bus.publish_command(routing_key="command.ionode.inbound.fetch", command=command)

        # FIX: Assert against the JSON-serialized dictionary representation
        expected_payload = json.loads(command.model_dump_json())
        dummy_handler.mock.assert_called_once_with(expected_payload)


@pytest.mark.asyncio
async def test_publish_event():
    broker = RabbitBroker()

    dummy_evt_queue = RabbitQueue("dummy_evt_queue", routing_key="event.resource.created")

    @broker.subscriber(queue=dummy_evt_queue, exchange=events_exchange)
    async def dummy_handler(msg: ResourceCreatedEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        event = ResourceCreatedEvent(
            header=MessageHeader(correlation_id="test-456", source_component="test"),
            resource_uri="local://test-uuid",
            mime_type="application/json"
        )

        await bus.publish_event(routing_key="event.resource.created", event=event)

        # FIX: Assert against the JSON-serialized dictionary representation
        expected_payload = json.loads(event.model_dump_json())
        dummy_handler.mock.assert_called_once_with(expected_payload)
