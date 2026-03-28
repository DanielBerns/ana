from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

# ==========================================
# BASE OBSERVABILITY SCHEMA
# ==========================================
class BaseEvent(BaseModel):
    """
    The foundational event schema.
    It ensures every single event passing through the broker has the required
    tracing data for extensive structured logging.
    """
    event_type: str
    # The correlation_id is generated once at the start of a workflow and
    # passed to all subsequent events to trace the entire lifecycle.
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# ==========================================
# 1. AUTONOMOUS SCRAPING EVENTS
# ==========================================
class PerceptionGathered(BaseEvent):
    """Published by the Interface after a scheduled task."""
    event_type: Literal["PerceptionGathered"] = "PerceptionGathered"
    source_url: str
    uri: str  # The Claim Check URI pointing to the Store payload

# ==========================================
# 2. USER CHAT EVENTS
# ==========================================
class UserPromptReceived(BaseEvent):
    """Published by the Interface (Chat Bridge) when a user sends a message."""
    event_type: Literal["UserPromptReceived"] = "UserPromptReceived"
    user_id: str
    text: str

# ==========================================
# 3. CONTEXT (MEMORY) EVENTS
# ==========================================
class ContextRequested(BaseEvent):
    """Published by the Controller to fetch history before making a decision."""
    event_type: Literal["ContextRequested"] = "ContextRequested"
    user_id: Optional[str] = None
    query_reference: Optional[str] = None
    reply_to_topic: str  # Tells Memory where to send the response

class ContextProvided(BaseEvent):
    """Published by Memory in response to a ContextRequested event."""
    event_type: Literal["ContextProvided"] = "ContextProvided"
    user_id: Optional[str] = None
    # History could be a list of past messages or summarized state
    history: List[Dict[str, Any]] = Field(default_factory=list)

# ==========================================
# 4. DELEGATION & EXECUTION EVENTS
# ==========================================
class CommandIssued(BaseEvent):
    """Published by the Controller to instruct the Actor."""
    event_type: Literal["CommandIssued"] = "CommandIssued"
    instruction: str
    user_id: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class ActionRequired(BaseEvent):
    """Published by the Actor to trigger an external action via the Interface."""
    event_type: Literal["ActionRequired"] = "ActionRequired"
    action_type: str  # e.g., "reply_to_chat", "trigger_webhook"
    payload: str      # The actual text response or data to send
    user_id: Optional[str] = None

class TaskCompleted(BaseEvent):
    """Published by the Actor and consumed silently by Memory for logging."""
    event_type: Literal["TaskCompleted"] = "TaskCompleted"
    task_name: str
    status: Literal["success", "failure"]
    result_summary: str

# ==========================================
# 5. CONTROL PLANE & LIFECYCLE EVENTS
# ==========================================
class ConfigurationUpdated(BaseEvent):
    """Published by the Configurator or Admin to trigger a runtime config reload."""
    event_type: Literal["ConfigurationUpdated"] = "ConfigurationUpdated"
    target_component: str  # e.g., "interface", "actor", or "all"
    new_configuration: dict[str, Any]

class SystemFatalError(BaseEvent):
    """Published by any component that encounters an unrecoverable state (e.g., bad config)."""
    event_type: Literal["SystemFatalError"] = "SystemFatalError"
    component: str
    error_reason: str
    bad_configuration: dict[str, Any]


# ==========================================
# 6. STORAGE & DATA LIFECYCLE EVENTS
# ==========================================
class PayloadStored(BaseEvent):
    """Emitted by the Store immediately after a file is saved and deduplicated."""
    event_type: Literal["PayloadStored"] = "PayloadStored"
    hash_id: str
    uri: str
    mime_type: str
    collection_id: Optional[str] = None
    size_bytes: int

class ModifyFileRetention(BaseEvent):
    """Consumed by the Store to dynamically change a file's lifecycle."""
    event_type: Literal["ModifyFileRetention"] = "ModifyFileRetention"
    hash_id: str
    new_policy: Literal["ephemeral", "standard", "preserved"]
