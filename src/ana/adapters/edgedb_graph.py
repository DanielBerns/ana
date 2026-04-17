# ana/adapters/gel_graph.py
import gel
from typing import Any

from ana.ports.interfaces import KnowledgeGraphPort
from ana.domain.tuples import Tuple4, SPOCTuple, EAVTTuple


class EdgeDBKnowledgeGraph(KnowledgeGraphPort):
    def __init__(self):
        # Automatically connects using gel project configuration
        self.client = gel.create_async_client()

    async def merge_tuples(self, tuples: list[Tuple4]) -> None:
        """Idempotently writes 4-tuples using EdgeQL 'unless conflict'."""

        # In a production environment, this should be executed in a transaction
        # or batched using `with` blocks in EdgeQL for performance.
        async for tx in self.client.transaction():
            async with tx:
                for t in tuples:
                    if isinstance(t, SPOCTuple):
                        await tx.query(
                            """
                            insert SPOCTuple {
                                subject := <str>$subject,
                                predicate := <str>$predicate,
                                object_ := <str>$object_,
                                context := <str>$context
                            } unless conflict;
                        """,
                            subject=t.subject,
                            predicate=t.predicate,
                            object_=t.object_,
                            context=t.context,
                        )

                    elif isinstance(t, EAVTTuple):
                        await tx.query(
                            """
                            insert EAVTTuple {
                                entity := <str>$entity,
                                attribute := <str>$attribute,
                                value := <str>$value,
                                timestamp := <datetime>$timestamp
                            } unless conflict;
                        """,
                            entity=t.entity,
                            attribute=t.attribute,
                            value=str(t.value),
                            timestamp=t.timestamp,
                        )

    async def query(
        self, query_string: str, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Executes read queries for Reasoner pathfinding and rule engines."""
        # Note: In EdgeDB, we return JSON and parse it to standard dicts
        json_result = await self.client.query_json(query_string, **parameters)
        import json

        return json.loads(json_result)
