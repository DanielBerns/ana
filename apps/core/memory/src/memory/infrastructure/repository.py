from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..domain.models import EventLog, Entity, NamedGraph, Quad

class MemoryRepository:
    """Outbound adapter for persisting and retrieving state from the PostgreSQL Quad-Store."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- 1. DETERMINISTIC LEDGER ---

    async def log_event(self, correlation_id: str, event_type: str, payload: dict) -> None:
        """Archives an event payload into the deterministic, append-only ledger."""
        new_log = EventLog(
            correlation_id=correlation_id,
            event_type=event_type,
            payload=payload
        )
        self.session.add(new_log)
        await self.session.commit()

    async def get_recent_history(self, limit: int = 5) -> list[dict]:
        """Fetches the most recent chronological events to build context."""
        stmt = select(EventLog).order_by(EventLog.timestamp.desc()).limit(limit)
        result = await self.session.execute(stmt)
        logs = [row.payload for row in result.scalars()]
        logs.reverse()
        return logs

    # --- 2. MULTIDIMENSIONAL KNOWLEDGE GRAPH (QUAD-STORE) ---

    async def ensure_graph_exists(self, graph_id: str, description: str = None) -> NamedGraph:
        """Ensures the 4th Dimension (Context) exists before asserting facts into it."""
        stmt = select(NamedGraph).where(NamedGraph.id == graph_id)
        result = await self.session.execute(stmt)
        graph = result.scalar_one_or_none()

        if not graph:
            graph = NamedGraph(id=graph_id, description=description)
            self.session.add(graph)
            await self.session.flush() # Flush to get the ID without committing the transaction yet
        return graph

    async def ensure_entity_exists(self, entity_id: str, entity_type: str, name: str) -> Entity:
        """Ensures a semantic node exists in the graph."""
        stmt = select(Entity).where(Entity.id == entity_id)
        result = await self.session.execute(stmt)
        entity = result.scalar_one_or_none()

        if not entity:
            entity = Entity(id=entity_id, entity_type=entity_type, name=name)
            self.session.add(entity)
            await self.session.flush()
        return entity

    async def assert_quad(
        self,
        subject_id: str,
        predicate: str,
        graph_id: str,
        correlation_id: str,
        object_entity_id: str = None,
        object_literal_value: str = None,
        confidence: float = 1.0
    ) -> Quad:
        """
        Asserts a 4-tuple fact (s, p, o, g) into the Knowledge Graph.
        Enforces the dual-object constraint (either IRI or Literal, not both).
        """
        if bool(object_entity_id) == bool(object_literal_value):
            raise ValueError("A Quad must have exactly one object: either an entity reference OR a literal value.")

        quad = Quad(
            subject_id=subject_id,
            predicate=predicate,
            object_entity_id=object_entity_id,
            object_literal_value=object_literal_value,
            graph_id=graph_id,
            confidence=confidence,
            source_correlation_id=correlation_id
        )
        self.session.add(quad)
        await self.session.commit()
        return quad
