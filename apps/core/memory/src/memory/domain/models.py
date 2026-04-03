import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, ForeignKey, JSON, DateTime, Index, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Entity(Base):
    """A distinct node in Ana's world model (e.g., a User, a Webpage, a Concept)."""
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class NamedGraph(Base):
    """
    The 4th Dimension (G): Defines the context, provenance, or temporal boundary of facts.
    Examples: "session:architect_01" or "source:https://example.com/news"
    """
    __tablename__ = "named_graphs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Quad(Base):
    """
    The Multidimensional Belief (Subject -> Predicate -> Object, within Graph).
    Includes property-graph metadata (confidence, correlation_id) on the edge itself.
    """
    __tablename__ = "quads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # (S) Subject
    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)

    # (P) Predicate
    predicate: Mapped[str] = mapped_column(String, index=True)

    # (O) Object - Dual Approach (IRI vs Literal)
    object_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), nullable=True)
    object_literal_value: Mapped[str | None] = mapped_column(String, nullable=True)

    # (G) Graph / Context
    graph_id: Mapped[str] = mapped_column(ForeignKey("named_graphs.id", ondelete="CASCADE"), index=True)

    # Neurosymbolic Hooks (Statistical confidence & Audit trail)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_correlation_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Enforce that an Object is EITHER a reference to another Entity OR a literal string, never both/neither.
        CheckConstraint(
            "(object_entity_id IS NULL AND object_literal_value IS NOT NULL) OR (object_entity_id IS NOT NULL AND object_literal_value IS NULL)",
            name="check_exclusive_object"
        ),
        # 1. SPOG Index (Optimized for forward graph traversals)
        Index("idx_quads_spog", "subject_id", "predicate", "object_entity_id", "graph_id"),

        # 2. POGS Index (Optimized for reverse lookups and property queries)
        Index("idx_quads_pogs", "predicate", "object_entity_id", "graph_id", "subject_id"),

        # 3. GPSO Index (Optimized for isolating facts within a specific Context/Graph)
        Index("idx_quads_gpso", "graph_id", "predicate", "subject_id", "object_entity_id"),
    )

class EventLog(Base):
    """Deterministic, append-only ledger of everything that has happened."""
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
