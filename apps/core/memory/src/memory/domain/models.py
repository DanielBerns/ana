import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, ForeignKey, JSON, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Entity(Base):
    """A distinct node in Ana's world model (e.g., a User, a Webpage, a Concept)."""
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String, index=True) # e.g., "person", "url", "concept"
    name: Mapped[str] = mapped_column(String, index=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict) # Flexible storage for statistical features
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Triple(Base):
    """
    A directional belief / logical relation (Subject -> Predicate -> Object).
    This forms the edges of the Knowledge Graph.
    """
    __tablename__ = "triples"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    subject_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    predicate: Mapped[str] = mapped_column(String, index=True) # e.g., "requested_action", "is_located_in"
    object_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)

    # Neurosymbolic hook: The statistical probability that this belief is true (0.0 to 1.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    # Audit trail: Which event caused Ana to formulate this belief?
    source_correlation_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class EventLog(Base):
    """Deterministic, append-only ledger of everything that has happened."""
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
