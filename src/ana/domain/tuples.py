# src/domain/tuples.py
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class BaseTuple(BaseModel):
    # Makes the model immutable and hashable
    model_config = ConfigDict(frozen=True)


class SPOCTuple(BaseTuple):
    tuple_type: Literal["spoc"] = "spoc"
    subject: str
    predicate: str
    object_: str
    context: str


class EAVTTuple(BaseTuple):
    tuple_type: Literal["eavt"] = "eavt"
    entity: str
    attribute: str
    # Note: For hashability, 'value' must be a hashable type if you rely on built-in sets.
    # In Pydantic, frozen models hash their field values.
    value: Any
    timestamp: datetime


# Type alias for easier type hinting in ports
Tuple4 = SPOCTuple | EAVTTuple
