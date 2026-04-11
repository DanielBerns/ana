from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict

class DomainDecision(BaseModel):
    """Base abstract representation of a domain decision."""
    model_config = ConfigDict(frozen=True)

class ActionDecision(DomainDecision):
    action_type: str
    payload: str

class CommandDecision(DomainDecision):
    instruction: str
    context_data: Dict[str, Any] = Field(default_factory=dict)
