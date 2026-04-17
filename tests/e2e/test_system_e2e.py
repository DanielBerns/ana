# tests/e2e/test_system_e2e.py
import json
import asyncio
import pytest

from faststream import TestApp, ContextRepo
from faststream.rabbit import TestRabbitBroker, RabbitQueue

# Import the fully assembled app
from ana.application import app as base_app
from ana.adapters.faststream_bus import (
    FastStreamMessageBus,
    events_exchange,
    commands_exchange,
)
from ana.domain.messages import ExecuteIONodeCommand, ReportCreatedEvent, MessageHeader
from ana.adapters.local_storage import LocalResourceRepository
from tests.integration.test_domain_agents import FakeKnowledgeGraph


@pytest.fixture
def temp_repository(tmp_path):
    return LocalResourceRepository(base_dir=str(tmp_path))


@pytest.fixture
def fake_graph():
    return FakeKnowledgeGraph()


@pytest.mark.asyncio
async def test_full_system_pipeline(temp_repository, fake_graph):
    """
    E2E Test: Command -> InboundNode -> Event -> Processor -> Event -> Reasoner -> Event -> Reporter -> Event
    """
    broker = base_app.broker

    # We want to intercept the VERY LAST event in the chain to verify completion
    final_queue = RabbitQueue("e2e_final_queue", routing_key="event.report.created")

    @broker.subscriber(queue=final_queue, exchange=events_exchange)
    async def final_report_handler(msg: ReportCreatedEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)

        # Override the global context with our test dependencies
        @base_app.on_startup
        async def setup_test_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("repository", temp_repository)
            context.set_global("graph", fake_graph)

        async with TestApp(base_app):
            # 1. Fire the initial command that starts the whole process
            command = ExecuteIONodeCommand(
                header=MessageHeader(
                    correlation_id="e2e-run-1", source_component="TestRunner"
                ),
                target_node_id="node_1",
                parameters={},  # No failure flags, execute the happy path
            )

            await test_broker.publish(
                command,
                routing_key="command.ionode.inbound.fetch",
                exchange=commands_exchange,
            )

            # 2. Allow the async event loop enough time to cascade through all 4 nodes
            await asyncio.sleep(0.5)

            # 3. Assert the final event reached the end of the pipeline
            assert final_report_handler.mock.call_count == 1

            # 4. Verify the actual contents of the generated report
            emitted_payload = final_report_handler.mock.call_args[0][0]
            report_uri = emitted_payload["report_uri"]

            report_bytes = await temp_repository.fetch(report_uri)
            report_data = json.loads(report_bytes)

            assert report_data["title"] == "Ana System Status Report"

            # The reasoner should have deduced that "node_1" is "reliable"
            assert len(report_data["deductions"]) == 1
            # FIX: The source component from the initial command was "node_1"
            assert report_data["deductions"][0]["subject"] == "node_1"
            assert report_data["deductions"][0]["object_"] == "reliable"
