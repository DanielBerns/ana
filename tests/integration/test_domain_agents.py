# tests/integration/test_domain_agents.py
import json
import asyncio
import pytest

from faststream import FastStream, TestApp, ContextRepo
from faststream.rabbit import TestRabbitBroker, RabbitBroker, RabbitQueue

from ana.agents.domain_agents import domain_router
from ana.adapters.faststream_bus import FastStreamMessageBus, events_exchange
from ana.domain.messages import ResourceCreatedEvent, KnowledgeUpdatedEvent, MessageHeader
from ana.adapters.local_storage import LocalResourceRepository
from ana.domain.tuples import SPOCTuple

class FakeKnowledgeGraph:
    """An in-memory fake that implements the KnowledgeGraphPort protocol."""
    def __init__(self):
        self.merged_tuples = []

    async def merge_tuples(self, tuples):
        self.merged_tuples.extend(tuples)

    async def query(self, query_string, parameters):
        if "produced_data_status" in query_string:
            return [
                {"subject": t.subject, "object_": t.object_}
                for t in self.merged_tuples
                if t.predicate == "produced_data_status" and t.object_ == "success"
            ]
        elif "is_state" in query_string:
            return [
                {"subject": t.subject, "object_": t.object_}
                for t in self.merged_tuples
                if t.predicate == "is_state"
            ]
        return []


@pytest.fixture
def temp_repository(tmp_path):
    return LocalResourceRepository(base_dir=str(tmp_path))

@pytest.fixture
def fake_graph():
    return FakeKnowledgeGraph()


@pytest.mark.asyncio
async def test_processor_logic(temp_repository, fake_graph):
    broker = RabbitBroker()
    broker.include_router(domain_router)

    k_queue = RabbitQueue("dummy_k_queue", routing_key="event.knowledge.updated.processor")
    @broker.subscriber(queue=k_queue, exchange=events_exchange)
    async def dummy_knowledge_handler(msg: KnowledgeUpdatedEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)
        app = FastStream(broker)

        @app.on_startup
        async def setup_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("repository", temp_repository)
            context.set_global("graph", fake_graph)

        async with TestApp(app):
            test_payload = b'{"status": "success", "data": "Test data"}'
            uri = await temp_repository.save(test_payload, {"source": "test"})

            event = ResourceCreatedEvent(
                header=MessageHeader(correlation_id="corr-1", source_component="TestNode"),
                resource_uri=uri,
                mime_type="application/json"
            )

            await test_broker.publish(event, routing_key="event.resource.created", exchange=events_exchange)
            await asyncio.sleep(0.1)

            # FIX: Expect at least 1 tuple (since the reasoner also cascaded and added a 2nd)
            assert len(fake_graph.merged_tuples) >= 1

            # FIX: specifically extract the tuple the Processor wrote to verify it
            written_tuple = next(t for t in fake_graph.merged_tuples if t.predicate == "produced_data_status")
            assert written_tuple.subject == "TestNode"
            assert written_tuple.object_ == "success"

            assert dummy_knowledge_handler.mock.call_count == 1


@pytest.mark.asyncio
async def test_reasoner_logic(fake_graph):
    broker = RabbitBroker()
    broker.include_router(domain_router)

    r_queue = RabbitQueue("dummy_r_queue", routing_key="event.knowledge.updated.reasoner")
    @broker.subscriber(queue=r_queue, exchange=events_exchange)
    async def dummy_reasoner_handler(msg: KnowledgeUpdatedEvent):
        pass

    async with TestRabbitBroker(broker) as test_broker:
        bus = FastStreamMessageBus(test_broker)
        app = FastStream(broker)

        @app.on_startup
        async def setup_context(context: ContextRepo):
            context.set_global("bus", bus)
            context.set_global("graph", fake_graph)

        async with TestApp(app):
            # FIX: Seed the graph with an actual SPOCTuple so the smart query finds it
            fake_graph.merged_tuples.append(
                SPOCTuple(
                    subject="TestNode",
                    predicate="produced_data_status",
                    object_="success",
                    context="processor_ingestion"
                )
            )

            event = KnowledgeUpdatedEvent(
                header=MessageHeader(correlation_id="corr-2", source_component="ProcessorNode"),
                subgraph_id="processor_ingestion",
                tuple_count=1
            )

            await test_broker.publish(event, routing_key="event.knowledge.updated.processor", exchange=events_exchange)
            await asyncio.sleep(0.1)

            # FIX: Assert len == 2 (the seeded tuple + the newly deduced tuple)
            assert len(fake_graph.merged_tuples) == 2

            deduced_tuple = next(t for t in fake_graph.merged_tuples if t.predicate == "is_state")
            assert deduced_tuple.subject == "TestNode"
            assert deduced_tuple.object_ == "reliable"

            assert dummy_reasoner_handler.mock.call_count == 1
