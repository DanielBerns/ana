### 1. Identified Gaps & Errors

* **Error: The "Fail Fast" Crash Loop:** You noted that if an adapter encounters an error, it crashes the instance and RabbitMQ NACKs the message to a Dead Letter Exchange (DLX). **The issue:** If the consumer crashes *before* issuing the NACK, RabbitMQ will simply requeue the message when the socket closes. When Docker restarts the instance, it will pick up the same poison pill, resulting in an infinite crash loop. 
    * *Fix:* The adapter must catch the exception at the highest boundary level, explicitly issue a `basic_reject` or `basic_nack` with `requeue=False`, acknowledge the DLX routing, and *then* gracefully shut down or continue processing.
* **Gap: The Polling Contradiction (Phase 7 vs. Phase 2):** In Component Workflow #2, Sensors are triggered by a `FetchCommand` from RabbitMQ. However, Phase 7 describes a Sensor that wakes up on an internal `execution_schedule` (cron) to poll an API.
    * *Fix:* To maintain strict event-driven purity, the Sensor should remain stateless. Introduce a lightweight **Scheduler Component** (e.g., using Celery beat or a simple cron container) whose sole job is to publish a `FetchCommand` to RabbitMQ every 60 seconds. The Sensor purely reacts to this command.
* **Gap: Missing Event Schemas (Contracts):** The system relies heavily on routing keys (`event.resource.created`), but there is no definition of the standard payload. Without a strict contract, Processors will fail unpredictably when parsing payloads from different Sensors.
    * *Fix:* Define a centralized `BaseEvent` and `BaseCommand` schema using Pydantic, enforcing fields like `event_id`, `timestamp`, `correlation_id`, and `payload`.
* **Gap: Idempotency:** RabbitMQ guarantees *at-least-once* delivery. Network blips can cause duplicate `ResourceCreatedEvent` or `KnowledgeUpdatedEvent` deliveries. 
    * *Fix:* Processors and Reasoners must be idempotent. The Graph DB operations should utilize `MERGE` (if using Cypher) or similar UPSERT logic based on a composite hash of the 4-tuples to prevent data duplication.

---

### 2. Interface Design (The Ports)

Using Python's `typing.Protocol` (which supports duck-typing and is often cleaner than `abc.ABC` for Hexagonal architectures), here is the proposed design for the core boundaries:

```python
from typing import Protocol, Any
from pydantic import BaseModel

# --- Shared DTOs (Data Transfer Objects) ---
class EventMessage(BaseModel):
    event_id: str
    routing_key: str
    payload: dict[str, Any]

class CommandMessage(BaseModel):
    command_id: str
    routing_key: str
    payload: dict[str, Any]

# --- 1. The Communication Backbone ---
class MessageBusPort(Protocol):
    def publish_event(self, event: EventMessage) -> None:
        """Publishes an event to the Topic Exchange."""
        ...

    def publish_command(self, command: CommandMessage) -> None:
        """Publishes a command to the Command Exchange."""
        ...

    def subscribe(self, routing_key: str, handler: callable) -> None:
        """Binds a queue to a routing key and listens."""
        ...

# --- 2. The Storage Mechanism ---
class ResourceRepositoryPort(Protocol):
    def save(self, stream: bytes, metadata: dict[str, Any]) -> str:
        """Saves raw bytes and returns a unique resource URI/ID."""
        ...

    def fetch(self, resource_uri: str) -> bytes:
        """Retrieves raw bytes using the URI/ID."""
        ...

# --- 3. The Knowledge Graph ---
class Tuple4(BaseModel):
    # Can be subclassed for SPOC (Subject, Predicate, Object, Context) 
    # or EAVT (Entity, Attribute, Value, Timestamp)
    pass 

class KnowledgeGraphPort(Protocol):
    def merge_tuples(self, tuples: list[Tuple4]) -> None:
        """Idempotently writes 4-tuples to the graph."""
        ...

    def query(self, query_string: str) -> list[dict[str, Any]]:
        """Executes a read query for Reasoner pathfinding/inference."""
        ...
```

---

### 3. Updated Execution Roadmap

Here are the refined prompts, adjusted to fix the architectural gaps and ensure the LLM generates production-ready code without conflating implementations with testing mocks.

**Phase 1: The Communication Backbone & Contracts**
> "I am building a Python-based Hexagonal Architecture. First, define generic Pydantic models for `EventMessage` and `CommandMessage` requiring fields like `id`, `correlation_id`, and `payload`. Second, design the 'Port' (`typing.Protocol`) for a Message Bus. Third, provide a concrete 'Adapter' implementation using RabbitMQ (via Aio_pika). It must support publishing and subscribing. Crucially, implement a strict 'Fail Fast' error handling strategy: if a subscriber's handler raises an exception, the adapter must explicitly NACK the message with `requeue=False` to route it to a Dead Letter Exchange to prevent crash loops. Provide Pytest unit tests using a mocked RabbitMQ connection."

**Phase 2: The Inbound Boundary (Stateless Sensor)**
> "Design the 'Sensor' component for an event-driven system as a strict inbound adapter. The Sensor must not have its own internal timer. It initializes using a validated YAML configuration (via Pydantic). It subscribes to a 'FetchCommand' via a injected `MessageBusPort`. Upon receiving the command, it executes the fetch, saves the payload using an injected `ResourceRepositoryPort`, and publishes a 'ResourceCreatedEvent' via the `MessageBusPort`. Ensure clean dependency injection. Provide a Pytest suite that mocks the Ports to verify the workflow."

**Phase 3: The Data Structure & Idempotency**
> "Design the core Domain Model for a Knowledge Graph that supports two types of 4-tuples: 1) Subject-Predicate-Object-Context and 2) Entity-Attribute-Value-Timestamp. Propose a Python class structure using Pydantic that cleanly represents both polymorphically. Define the `KnowledgeGraphPort` (`typing.Protocol`) for these tuples, specifically requiring a `merge_tuples` method to guarantee idempotent UPSERTs. Provide examples of how a Processor would validate these tuples before passing them to the Port."

**Phase 4: The ML Reasoner Interface**
> "Design the 'Reasoner' component for a Python event-driven architecture. A Reasoner is a pure Python ML agent that reacts to a 'KnowledgeUpdatedEvent'. Define an abstract base class that forces the implementation of an `infer` method. Provide a concrete example of a Reasoner that uses an injected `KnowledgeGraphPort` to find shortest paths between nodes, deduces new 4-tuples, and publishes a new 'KnowledgeUpdatedEvent' via an injected `MessageBusPort`. Ensure the execution is idempotent. Include unit tests mocking the Graph and Bus."

**Phase 5: Strict Foreign Boundaries**
> *(Keep this prompt exactly as you originally wrote it; it is perfectly scoped.)*

**Phase 6: The Admin CLI Tooling**
> *(Keep this prompt exactly as you originally wrote it; it separates administration beautifully.)*

**Phase 7: The Concrete API Polling Sensor**
> "I am building a Python-based Sensor component. The Sensor acts as an Inbound Adapter that fetches from a 'FrontendSource' REST API. It is triggered by receiving a `FetchCommand` with a payload defining the `batch_size`. 
> 
> Implement the following strict workflow:
> 1. Fetch a `/resources` metadata endpoint. Parse the results and strictly ignore any resource where `size_bytes` exceeds 50MB (log a warning).
> 2. For allowed resources, download the payload into memory. Use the `python-magic` library to read the first 2048 bytes. Verify the true MIME type against a hardcoded whitelist (e.g., pdf, mp4, jpeg, plain text). If invalid, drop the buffer and log an AdapterError.
> 3. For validated files, use an injected `ResourceRepositoryPort` to save the file, and an injected `MessageBusPort` to publish a `ResourceCreatedEvent`. 
> Provide the Python implementation using strict dependency injection, and Pytest unit tests that mock the HTTP responses and the Ports."


##################################################################################################2

### Draft Design: Ana's Architecture

Here is a revised workflow

**Core Principles Applied:**
* **Hexagonal Architecture:** The domain logic (Processors/Reasoners) is completely isolated from the infrastructure (RabbitMQ, HTTP, SQLAlchemy, Postgres).
* **Command/Event Segregation:** We differentiate between *Commands* (do this) and *Events* (this happened). 
* **Fail Fast:** If an adapter encounters an unexpected state, it throws an exception, crashes the instance, and relies on the orchestrator (like Docker) to restart it, while RabbitMQ automatically NACKs (negative acknowledgements) the message and routes it to a Dead Letter Exchange.

**Component Workflow:**

1. **The Infrastructure Layer (RabbitMQ):**
   * Acts as the single source of truth for communication.
   * Utilizes Topic Exchanges to route messages based on routing keys (e.g., `event.resource.created`, `command.sensor.fetch`).

2. **TimeNode**
   * They read their YAML config, and emit a sequence of periodic `IONodeExecuteEvent` (period and event definition in the YAML config)
   * They react to StartEvent, PauseEvent, ResumeEvent, and StopEvent.

3. **IONode (Adapters):**
   * They read their YAML config, execute a task (interchanging info with one external website, or read/write operations in a local directory)
   * They may push a raw payload to the ResourceRepository: in this case, if they receive a resource_uri from the ResourceRepository, then they emit a `ResourceCreatedEvent` to the event queue, or if they don't receive a resource_uri from the ResourceRepository, then they emit a `IONodeFailureEvent` and stop).
   * The IONodes interact with associated websites and non associated websites: In the case of associated websites information transfer may be bidirectional (for example, if the IONode gets a document from the associated website, the IONode may post the resource_uri to the website). 
   * Triggered by a specific `IONodeExecuteEvent`.

4. **ResourceRepository (Storage Adapter):**
   * A pure storage mechanism (blob storage, S3, or local disk). It does not emit events itself; the IONode handle that upon successful storage.

5. **Processors (The Domain Core):**
   * Subscribe to `ResourceCreatedEvent` and `ResourceUpdatedEvent`.
   * They parse the raw data and apply deterministic transformations.
   * If a Processor detects missing context, it emits a `IONodeExecuteCommand` back to the event queue (targeting a specific IONode).
   * Upon successful processing, they write 4-tuples to the Knowledge Graph and emit a `KnowledgeUpdatedEvent` to the event queue, they may write the ResourceRepository and  emit a `ResourceCreatedEvent` to the event queue, and they may update the ResourceRepository and emit a `ResourceUpdatedEvent` to the event queue.

5. **Reasoners (The AI Domain Core):**
   * Subscribe to `KnowledgeUpdatedEvent`.
   * These are pure Python ML agents. They read sub-graphs from the Knowledge Graph, run some algorithms, and write *new* deduced 4-tuples back to the graph, emiting some special `KnowledgeUpdatedEvent`
   * They may emit `IONodeExecuteCommand` to the event queue

6. **Reporters:**
   * Subscribe to specific `KnowledgeUpdatedEvent` routing keys.
   * When triggered, they format the data and create a resource in ResourceRepository, emiting a `ReportCreatedEvent` and maybe `IONodeExecuteEvent`

---

### Execution Roadmap: Mini-Project Prompts

To prevent bloat and ensure testability, you should build Ana from the inside out. Copy and paste these prompts into new chat sessions to generate the isolated components. 

**Phase 1: The Communication Backbone**
> **Prompt 1:** "I am building a Python-based Hexagonal Architecture. Design the 'Port' (Interface/ABC) for a Message Bus, and provide a concrete 'Adapter' implementation using RabbitMQ (via Pika or Aio_pika). It must support publishing 'Events' and subscribing to 'Commands'. Include a strict 'Fail Fast' error handling strategy where unhandled exceptions cause the message to be routed to a Dead Letter Queue. Provide the unit tests using pytest and a mocked RabbitMQ connection."

**Phase 2: The Inbound Boundary**
> **Prompt 2:** "Design the 'Sensor' component for an event-driven system. The Sensor is an inbound adapter. Provide a Python implementation that initializes using a validated YAML configuration (use Pydantic). The Sensor must implement a start/stop lifecycle. It should listen for a 'FetchCommand', retrieve dummy data, save it using a generic 'ResourceRepository' Port, and finally publish a 'ResourceCreatedEvent' via a 'MessageBus' Port. Focus on clean dependency injection and provide a test suite."

**Phase 3: The Data Structure**
> **Prompt 3:** "Design the core Domain Model for a Knowledge Graph that supports two types of 4-tuples: 1) Subject-Predicate-Object-Context and 2) Entity-Attribute-Value-Timestamp. Propose a Python class structure that can cleanly represent both forms polymorphically. Then, define the 'Repository Port' (interface) for CRUD operations on these tuples. Provide examples of how a Processor would instantiate and validate these tuples before saving."

**Phase 4: The ML Reasoner Interface**
> **Prompt 4:** "Design the 'Reasoner' component for a Python-based event-driven architecture. A Reasoner is an ML agent that reacts to a 'KnowledgeUpdatedEvent'. Define an abstract base class for a Reasoner that forces the implementation of an 'infer' method. Provide a concrete example of a Reasoner that queries a 'KnowledgeGraph' Port to find shortest paths between nodes, and then generates new 4-tuples based on that inference. Include unit tests that mock the graph database."

**Phase 5: Strict Foreign Boundaries**
> **Prompt 5:** "I am building a Hexagonal Architecture system in Python. Design the strict 'Ports' (using `abc.ABC` or `typing.Protocol`) for a `ForeignSource` (Inbound) and a `ForeignTarget` (Outbound). Define Pydantic models for the generic data structures they must exchange with the core system, such as `AuthCredentials`, `QueryParameters`, and `StandardizedPayload`. Then, write one concrete implementation of a `ForeignSource` adapter that mocks fetching data from a REST API, proving it strictly adheres to the Port."

**Phase 6: The Admin CLI Tooling**
> **Prompt 6:** "Design a lightweight, stateless Command Line Interface (CLI) in Python using the `Click` or `Typer` library to act as an administrative tool for an event-driven system. The CLI should not connect directly to the system's databases. Instead, implement commands to: 1) Generate a dummy JWT auth token, 2) Publish a manual 'WakeUp' command to a RabbitMQ queue to manually trigger a system component, and 3) Tail system logs. Provide the implementation and tests."


---

### Phase 7 The Polling Sensor Mini-Project

> **Prompt 7:** "I am building a Python-based Sensor component for an event-driven Hexagonal Architecture. The Sensor acts as an Inbound Adapter that polls a 'FrontendSource' REST API for resources. Initialize the Sensor with a YAML configuration that includes API credentials, a `poll_interval` of 60 seconds, and a `max_batch_size` of 10. 
> 
> Implement the following strict 'fail fast' workflow:
> 1. Poll a `/resources` metadata endpoint. Parse the results and strictly ignore any resource where `size_bytes` exceeds 50MB.
> 2. For the allowed resources, download the payload. Use the `python-magic` library to read the file's magic bytes. Verify the true MIME type against a hardcoded whitelist (e.g., pdf, mp4, jpeg, plain text). If invalid, discard the file.
> 3. For successfully validated files, mock saving them to a generic 'ResourceRepository' Port and mock publishing a 'ResourceCreatedEvent' via a 'MessageBus' Port. Provide the Python implementation and Pytest unit tests, mocking the HTTP responses."

#### 1. Enforcing the 50MB Limit (Metadata First)
In the polling model, the Sensor must never blindly download a file. 
* The Sensor first calls the `GET /resources?cursor=...` endpoint.
* It parses the returned `ResourceMetadata` array. 
* Before making the second call to download the actual bytes, it checks the `size_bytes` field. If the size is greater than 50MB (52,428,800 bytes), the Sensor simply ignores the resource, logs a `SizeLimitExceeded` warning, and moves to the next item.

#### 2. Validating the MIME Type (Trust, but Verify)
Even if the FrontendSource is an associated project, you cannot assume its database is free of corruption or bad user uploads. 
* The Sensor calls `GET /resources/{resourceId}/content` to download the file into a temporary buffer.
* The Sensor immediately runs `python-magic` on the first 2048 bytes of the buffer. 
* If the true magic bytes do not match the expected MIME type from the metadata (or if it falls outside your allowed list of txt, pdf, mp4, etc.), the Sensor drops the buffer, logs an `AdapterError`, and refuses to publish a `ResourceCreatedEvent`.

#### 3. Rate Limiting: 10 Files / Minute (Self-Throttling)
Instead of relying on a Redis rate-limiter to block incoming webhooks, the Sensor enforces this limit internally based on its YAML configuration.
* You configure the Sensor's `execution_schedule` to wake up exactly once every minute.
* You configure a parameter `max_batch_size: 10`.
* When the Sensor polls, it appends `?limit=10` to the FrontendSource API call. It processes those 10 files, updates its pagination cursor, and goes back to sleep. Ana never ingests more than 10 files per minute per Sensor, effectively solving backpressure at the source.
