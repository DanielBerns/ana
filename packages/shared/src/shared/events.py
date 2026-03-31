from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class BaseEvent(BaseModel):
    event_type: str
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PerceptionGathered(BaseEvent):
    event_type: Literal["PerceptionGathered"] = "PerceptionGathered"
    source_url: str
    uri: str

class UserPromptReceived(BaseEvent):
    event_type: Literal["UserPromptReceived"] = "UserPromptReceived"
    user_id: str
    text: str

class ContextRequested(BaseEvent):
    event_type: Literal["ContextRequested"] = "ContextRequested"
    user_id: Optional[str] = None
    query_reference: Optional[str] = None
    reply_to_topic: str

class ContextProvided(BaseEvent):
    event_type: Literal["ContextProvided"] = "ContextProvided"
    user_id: Optional[str] = None
    history: List[Dict[str, Any]] = Field(default_factory=list)
    # FIX: Added trigger_event to the Pydantic schema to prevent serialization drops
    trigger_event: Optional[Dict[str, Any]] = None

class CommandIssued(BaseEvent):
    event_type: Literal["CommandIssued"] = "CommandIssued"
    instruction: str
    user_id: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class ActionRequired(BaseEvent):
    event_type: Literal["ActionRequired"] = "ActionRequired"
    action_type: str
    payload: str
    user_id: Optional[str] = None

class TaskCompleted(BaseEvent):
    event_type: Literal["TaskCompleted"] = "TaskCompleted"
    task_name: str
    status: Literal["success", "failure"]
    result_summary: str

class ConfigurationUpdated(BaseEvent):
    event_type: Literal["ConfigurationUpdated"] = "ConfigurationUpdated"
    target_component: str
    new_configuration: dict[str, Any]

class SystemFatalError(BaseEvent):
    event_type: Literal["SystemFatalError"] = "SystemFatalError"
    component: str
    error_reason: str
    bad_configuration: dict[str, Any]

class PayloadStored(BaseEvent):
    event_type: Literal["PayloadStored"] = "PayloadStored"
    hash_id: str
    uri: str
    mime_type: str
    collection_id: Optional[str] = None
    size_bytes: int

class ModifyFileRetention(BaseEvent):
    event_type: Literal["ModifyFileRetention"] = "ModifyFileRetention"
    hash_id: str
    new_policy: Literal["ephemeral", "standard", "preserved"]
