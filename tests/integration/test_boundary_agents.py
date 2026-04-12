# tests/integration/test_boundary_agents.py
import json
import asyncio
import pytest

from faststream import FastStream, TestApp, ContextRepo
from faststream.rabbit import TestRabbitBroker, RabbitBroker, RabbitQueue

from ana.agents.inbound_node import (inbound_router, handle_inbound_command)
from ana.adapters.faststream_bus import FastStreamMessageBus, events_exchange, commands_exchange
from ana.domain.messages import ExecuteIONodeCommand, ResourceCreatedEvent, IONodeFailureEvent, MessageHeader
from ana.adapters.local_storage import LocalResourceRepository


@pytest.fixture
def temp_repository(tmp_path):
    """Provides a fresh local storage repository for testing."""
    return LocalResourceRepository(base_dir=str(tmp_path))


@pytest.mark.asyncio
async def test_inbound_node_success(temp_repository):
    broker = RabbitBroker()
    broker.include_router(inbound_router)

    evt_queue = RabbitQueue("dummy_evt_queue", routing_key="event.resource.created")
    @broker.subscriber(queue=evt_queue, exchange=events_exchange)
    async def dummy_event_handler(msg: ResourceCreatedEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        app = FastStream(broker)

        @app.on_startup
        async def setup_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("repository", temp_repository)

        async with TestApp(app):

            command = ExecuteIONodeCommand(
                header=MessageHeader(correlation_id="corr-999", source_component="test"),
                target_node_id="node_1",
                parameters={}
            )

            # FIX: Explicitly target the commands_exchange so it routes correctly
            await test_broker.publish(
                command,
                routing_key="command.ionode.inbound.fetch",
                exchange=commands_exchange
            )

            await asyncio.sleep(0.1)

            assert dummy_event_handler.mock.call_count == 1

            emitted_payload = dummy_event_handler.mock.call_args[0][0]
            resource_uri = emitted_payload["resource_uri"]

            assert resource_uri.startswith("local://")
            fetched_bytes = await temp_repository.fetch(resource_uri)
            assert fetched_bytes == b'{"status": "success", "data": "Sample external data"}'


@pytest.mark.asyncio
async def test_inbound_node_expected_failure(temp_repository):
    broker = RabbitBroker()
    broker.include_router(inbound_router)

    fail_queue = RabbitQueue("dummy_fail_queue", routing_key="event.ionode.failed")
    @broker.subscriber(queue=fail_queue, exchange=events_exchange)
    async def dummy_fail_handler(msg: IONodeFailureEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        app = FastStream(broker)
        @app.on_startup
        async def setup_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("repository", temp_repository)

        async with TestApp(app):

            command = ExecuteIONodeCommand(
                header=MessageHeader(correlation_id="corr-999", source_component="test"),
                target_node_id="node_1",
                parameters={"simulate_api_down": True}
            )

            # FIX: Explicitly target the commands_exchange
            await test_broker.publish(
                command,
                routing_key="command.ionode.inbound.fetch",
                exchange=commands_exchange
            )

            await asyncio.sleep(0.1)

            assert dummy_fail_handler.mock.call_count == 1
            payload = dummy_fail_handler.mock.call_args[0][0]
            assert payload["error_reason"] == "External API returned 503 Unavailable."


@pytest.mark.asyncio
async def test_inbound_node_unexpected_failure(temp_repository):
    broker = RabbitBroker()
    broker.include_router(inbound_router)

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        app = FastStream(broker)
        @app.on_startup
        async def setup_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("repository", temp_repository)

        async with TestApp(app):

            command = ExecuteIONodeCommand(
                header=MessageHeader(correlation_id="corr-999", source_component="test"),
                target_node_id="node_1",
                parameters={"simulate_fatal_error": True}
            )

            from faststream.exceptions import RejectMessage
            with pytest.raises(RejectMessage):
                # FIX: Pass the dependencies directly to the handler since we are
                # invoking the Python function directly to catch the exception.
                await handle_inbound_command(command, repository=temp_repository, bus=bus)
