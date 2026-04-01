from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict

class BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True) # Enforce immutability

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
