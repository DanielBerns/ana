# src/agents/reporter_node.py
import json
from typing import Annotated

from faststream import Context
from faststream.rabbit import RabbitRouter, RabbitQueue
from faststream.exceptions import RejectMessage

from ana.adapters.faststream_bus import events_exchange
from ana.domain.messages import KnowledgeUpdatedEvent, ReportCreatedEvent, MessageHeader
from ana.ports.interfaces import (
    ResourceRepositoryPort,
    KnowledgeGraphPort,
    MessageBusPort,
)

reporter_router = RabbitRouter()

# The reporter specifically listens to the reasoner's output
reporter_queue = RabbitQueue(
    "ana.queue.reporters", routing_key="event.knowledge.updated.reasoner"
)


@reporter_router.subscriber(queue=reporter_queue, exchange=events_exchange)
async def handle_reasoner_update(
    event: KnowledgeUpdatedEvent,
    repository: Annotated[ResourceRepositoryPort, Context("repository")],
    graph: Annotated[KnowledgeGraphPort, Context("graph")],
    bus: Annotated[MessageBusPort, Context("bus")],
):
    """Compiles a report from deduced knowledge and saves it to the repository."""
    try:
        # 1. Query the graph for the newly deduced states
        query_string = """
            select SPOCTuple { subject, object_ }
            filter .predicate = 'is_state' and .context = 'reasoner_deduction';
        """
        results = await graph.query(query_string, {})

        # 2. Format the report
        report_data = {
            "title": "Ana System Status Report",
            "triggering_event": event.header.message_id,
            "deductions": results,
        }
        report_bytes = json.dumps(report_data, indent=2).encode("utf-8")

        # 3. Save the report via the Repository Port
        metadata = {"type": "system_report", "source_reasoner": event.reasoner_id}
        report_uri = await repository.save(report_bytes, metadata)

        # 4. Emit the ReportCreatedEvent
        r_event = ReportCreatedEvent(
            header=MessageHeader(
                correlation_id=event.header.correlation_id,
                source_component="ReporterNode",
            ),
            report_uri=report_uri,
            metadata=metadata,
        )
        await bus.publish_event(routing_key="event.report.created", event=r_event)

    except Exception as e:
        raise RejectMessage() from e
