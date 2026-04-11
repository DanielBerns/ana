# src/domain/messages.py
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def generate_utc_now() -> datetime:
    """Helper to ensure all timestamps are timezone-aware UTC."""
    return datetime.now(timezone.utc)


class MessageHeader(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str
    timestamp: datetime = Field(default_factory=generate_utc_now)
    source_component: str


class BaseCommand(BaseModel):
    header: MessageHeader
    command_type: str


class BaseEvent(BaseModel):
    header: MessageHeader
    event_type: str


# --- Specific Commands ---

class ExecuteIONodeCommand(BaseCommand):
    command_type: Literal["execute_ionode"] = "execute_ionode"
    target_node_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)


# --- Specific Events ---

class ResourceCreatedEvent(BaseEvent):
    event_type: Literal["resource_created"] = "resource_created"
    resource_uri: str
    mime_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeUpdatedEvent(BaseEvent):
    event_type: Literal["knowledge_updated"] = "knowledge_updated"
    subgraph_id: str
    reasoner_id: str | None = None
    tuple_count: int


class IONodeFailureEvent(BaseEvent):
    event_type: Literal["ionode_failure"] = "ionode_failure"
    node_id: str
    error_reason: str
