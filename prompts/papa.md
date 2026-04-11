### Finalized Design: Ana's Architecture

**Core Principles Applied:**
* **Hexagonal Architecture:** The domain logic (Processors/Reasoners) is completely isolated from the infrastructure (RabbitMQ, HTTP, SQLAlchemy, Postgres, Local File Systems).
* **Command/Event Segregation:** Strict adherence to CQRS. *Commands* (`ExecuteIONodeCommand`) mandate an action. *Events* (`ResourceCreatedEvent`) state an immutable historical fact.
* **Fail Fast & Explicit NACK:** If an adapter encounters an unexpected state, it catches the exception at the boundary, explicitly sends a NACK (`requeue=False`) to RabbitMQ so the message routes to a Dead Letter Exchange, and *then* crashes the instance to let the orchestrator restart it. This prevents infinite crash loops.

**Component Workflow:**

1. **The Infrastructure Layer (Message Broker):**
   * Acts as the single source of truth for communication.
   * Utilizes Topic Exchanges to route messages based on routing keys (e.g., `event.resource.created`, `command.ionode.inbound.fetch`).

2. **TimeNode (The Scheduler):**
   * A stateless trigger mechanism. It reads a YAML config and emits a sequence of periodic `ExecuteIONodeCommand` messages to the command queue. 
   * It reacts to `StartCommand`, `PauseCommand`, `ResumeCommand`, and `StopCommand`.

3. **InboundIONode (Source Adapters):**
   * Strictly unidirectional. They wake up when triggered by a specific `ExecuteIONodeCommand`.
   * They execute a task (e.g., fetching from an external API or reading a local directory).
   * They push the raw payload to the `ResourceRepository`.
   * If successful (receiving a `resource_uri`), they emit a `ResourceCreatedEvent`. If they fail, they emit an `IONodeFailureEvent` and halt.

4. **OutboundIONode (Target Adapters):**
   * Strictly unidirectional. Triggered by specific Commands or Events.
   * They format and push data out of Ana's ecosystem (e.g., posting a URI to an associated website or writing an export file). 

5. **ResourceRepository (Storage Adapter):**
   * A pure storage mechanism (blob storage, S3, local disk). It does not emit events; the IONodes or Reporters handle that upon successful interaction.

6. **Processors (The Domain Core):**
   * Subscribe to `ResourceCreatedEvent` and `ResourceUpdatedEvent`.
   * Parse the raw data, apply deterministic transformations, and write 4-tuples to the Knowledge Graph.
   * Upon successful graph writes, they emit a `KnowledgeUpdatedEvent`.
   * If they detect missing context, they emit an `ExecuteIONodeCommand` to fetch the missing pieces.

7. **Reasoners (The Rule-Based Memory & AI Core):**
   * Subscribe to `KnowledgeUpdatedEvent`.
   * These are pure Python, deterministic rule-based agents. They query sub-graphs from the Knowledge Graph, run logic engines or pathfinding algorithms, and deduce *new* 4-tuples.
   * They write the new tuples back to the graph and emit specific `KnowledgeUpdatedEvent`s. 
   * They may emit `ExecuteIONodeCommand`s if the rules engine dictates external data is needed.

8. **Reporters:**
   * Subscribe to specific `KnowledgeUpdatedEvent` routing keys.
   * Format the deduced data, create a polished resource in the `ResourceRepository`, and emit a `ReportCreatedEvent`.

---

### Strict Interfaces: Pydantic & Protocols

To implement this cleanly, modern Python tooling like Pydantic for validation and `typing.Protocol` for dependency injection are ideal. If you are utilizing a framework like FastStream for the message broker adapter, these Pydantic models will map perfectly to its automated serialization and routing capabilities.

```python
from typing import Any, Protocol, Literal, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import uuid4

# ==========================================
# 1. BASE DTOs (Data Transfer Objects)
# ==========================================

class MessageHeader(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    source_component: str

class BaseCommand(BaseModel):
    header: MessageHeader
    command_type: str

class BaseEvent(BaseModel):
    header: MessageHeader
    event_type: str

# ==========================================
# 2. SPECIFIC COMMANDS & EVENTS
# ==========================================

class ExecuteIONodeCommand(BaseCommand):
    command_type: Literal["execute_ionode"] = "execute_ionode"
    target_node_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)

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

# ==========================================
# 3. KNOWLEDGE GRAPH 4-TUPLES
# ==========================================

class BaseTuple(BaseModel):
    model_config = ConfigDict(frozen=True) # Makes tuples hashable for idempotent UPSERTs

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
    value: Any
    timestamp: datetime

# Polymorphic type for the Graph Port
Tuple4 = Union[SPOCTuple, EAVTTuple]

# ==========================================
# 4. HEXAGONAL PORTS (Interfaces)
# ==========================================

class MessageBusPort(Protocol):
    """Outbound port for the domain to communicate with the broker."""
    async def publish_event(self, routing_key: str, event: BaseEvent) -> None:
        ...

    async def publish_command(self, routing_key: str, command: BaseCommand) -> None:
        ...

class ResourceRepositoryPort(Protocol):
    """Port for interacting with raw file storage."""
    async def save(self, stream: bytes, metadata: dict[str, Any]) -> str:
        """Returns the assigned resource_uri."""
        ...

    async def fetch(self, resource_uri: str) -> bytes:
        ...

class KnowledgeGraphPort(Protocol):
    """Port for the Deterministic Domain to interact with the Graph DB (e.g., Postgres/SQLAlchemy)."""
    async def merge_tuples(self, tuples: list[Tuple4]) -> None:
        """Idempotently writes 4-tuples. Must not duplicate existing data."""
        ...

    async def query(self, query_string: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Executes read queries for Reasoner pathfinding and rule engines."""
        ...
```
