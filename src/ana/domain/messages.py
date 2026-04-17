from uuid import uuid4
from typing import Any, List, Literal
from pathlib import Path
import yaml
from pydantic import BaseModel, Field
from datetime import datetime, timezone

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

class ScheduledAction(BaseModel):
    """Defines a single cron-triggered action for a node."""
    name: str
    cron: str
    parameters: dict[str, Any] = Field(default_factory=dict)

class ScheduledNode(BaseModel):
    """Groups multiple actions under a single target IO Node."""
    target_node_name: str
    actions: List[ScheduledAction] = Field(default_factory=list)

class SchedulerConfig(BaseModel):
    """The root configuration file."""
    nodes: List[ScheduledNode] = Field(default_factory=list)

class ExecuteIONodeCommand(BaseCommand):
    command_type: Literal["execute_ionode"] = "execute_ionode"
    target_node_name: str
    actions: List[ScheduledAction] = Field(default_factory=list)


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


class ReportCreatedEvent(BaseEvent):
    event_type: Literal["report_created"] = "report_created"
    report_uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)


