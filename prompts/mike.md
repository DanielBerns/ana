### Draft Design: Ana's Architecture

Here is the revised blueprint, mapping your requirements to strict boundaries and well-known patterns.

**Core Principles Applied:**
* **Hexagonal Architecture:** The domain logic (Processors/Reasoners) is completely isolated from the infrastructure (RabbitMQ, HTTP, Graph DB).
* **Command/Event Segregation:** We differentiate between *Commands* (do this) and *Events* (this happened). 
* **Fail Fast:** If an adapter encounters an unexpected state, it throws an exception, crashes the instance, and relies on the orchestrator (like Docker) to restart it, while RabbitMQ automatically NACKs (negative acknowledgements) the message and routes it to a Dead Letter Exchange.

**Component Workflow:**

1. **The Infrastructure Layer (RabbitMQ):**
   * Acts as the single source of truth for communication.
   * Utilizes Topic Exchanges to route messages based on routing keys (e.g., `event.resource.created`, `command.sensor.fetch`).

2. **Sensors (Inbound Adapters):**
   * Triggered by a `FetchCommand` from RabbitMQ.
   * They read their YAML config, execute the fetch, and push the raw payload to the ResourceRepository.
   * They emit a `ResourceCreatedEvent` to RabbitMQ. 

3. **ResourceRepository (Storage Adapter):**
   * A pure storage mechanism (blob storage, S3, or local disk). It does not emit events itself; the Sensors handle that upon successful storage.

4. **Processors (The Domain Core):**
   * Subscribe to `ResourceCreatedEvent`.
   * They parse the raw data and apply deterministic transformations.
   * If a Processor detects missing context, it emits a `FetchCommand` back to RabbitMQ (targeting a specific Sensor).
   * Upon successful processing, they write 4-tuples to the Knowledge Graph and emit a `KnowledgeUpdatedEvent` to RabbitMQ, they may write the ResourceRepository and  emit a `ResourceCreatedEvent` to RabbitMQ, and they may update the ResourceRepository and emit a `ResourceUpdatedEvent` to RabbitMQ.

5. **Reasoners (The ML Domain Core):**
   * Subscribe to `KnowledgeUpdatedEvent` or run on scheduled commands.
   * These are pure Python ML agents. They read sub-graphs from the Knowledge Graph, run pathfinding or inference algorithms, and write *new* deduced 4-tuples back to the graph.

6. **Actors (Outbound Adapters):**
   * Subscribe to specific `KnowledgeUpdatedEvent` routing keys.
   * When triggered, they format the data and push it to external targets.

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
