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

