Here is the complete, updated specification for Ana. I have bumped the version to v7.1 to reflect the corrections to the event choreography, accurately detailing both the autonomous scraping and the proxy chat flows, as well as fixing the Memory logging steps.

---

# "Ana" System Specification (v7.1)

## 1. System Overview
Ana is a distributed, agent-based system built on an **Event-Driven Architecture (EDA)**. Instead of point-to-point synchronous APIs, components communicate asynchronously by publishing and subscribing to a central Event Broker. The system isolates external communication, state management, and decision-making into network-partitioned services. It utilizes a shared "Claim Check" blob-storage pattern for heavy payloads to keep event streams highly performant, and mandates a Hexagonal Architecture for internal component design.

## 2. Core Components

1.  **Event Broker:** The central nervous system of Ana (e.g., Kafka, RabbitMQ, or Redis Streams). It manages message queues/topics, ensuring guaranteed delivery and buffering events if a component temporarily goes offline. *This replaces the Service Registry.*
2.  **Configurator:** A dynamic configuration and security server. It holds the startup state, scheduling parameters, and provisions authentication credentials for components to connect to the Event Broker and Store.
3.  **Controller:** The decision-making engine. It subscribes to external data events, requests historical state, and publishes execution commands.
4.  **Actor:** The execution engine. It subscribes to command events, performs the internal domain work, and publishes requests for external actions and operational records.
5.  **Interface:** The sensory, manipulation, and communication boundary. It is the *only* component with access outside the local network. It has two primary roles:
    * **Chat Bridge:** It connects to an external **Proxy Website**. The Proxy handles all human user authentication and session management. The Interface receives validated chat payloads from the Proxy, translates them into internal events, and pushes system responses back to the Proxy to be routed to the correct user.
    * **Autonomous Agent:** It houses an internal `cron`-based scheduler to autonomously scrape and poll external data sources as directed by the Configurator.
    *(Note: The Inspector remains a separate component. The Proxy Website is for general authorized users to interact with Ana's outputs, while the Inspector is for LAN-side system administrators to monitor Ana's internal database health.)*
6.  **Memory:** The central data store. It subscribes to operational records for silent logging and responds to context requests from decision-making components.
7.  **Store:** A specialized storage component with a standard HTTP Server API. It is used exclusively for large resources (e.g., scraped media, large datasets). It enforces an automated **Time-To-Live (TTL) garbage collection policy**.
8.  **Inspector:** A dedicated administrative user interface on the local network. It authenticates human users, aggregates system state, and allows deep inspection of component databases.

## 3. Internal Component Design: Hexagonal Architecture
To support multiple implementations and ensure framework independence, all core components must be built using **Hexagonal Architecture (Ports and Adapters)**. 

* **Domain Core:** The internal decision-making or execution logic remains completely agnostic to the network.
* **Driving Ports (Inbound):** Event Listeners (consumers) act as adapters that translate incoming broker messages into domain commands.
* **Driven Ports (Outbound):** Event Publishers (producers) and internal database drivers act as adapters, allowing the core to output results without knowing the specific broker or database technology.

## 4. Component Interactions & Event Flow

Communication is achieved by publishing discrete, immutable events to specific topics/streams on the Event Broker.

**4.1. The "Claim Check" Pattern**
Event brokers degrade if forced to carry megabytes of data. When a component (like the Interface) generates a large payload, it first `POST`s the file to the **Store** via HTTP. The Store returns a URI. The component then publishes its event to the Broker containing *only* the lightweight URI.

**4.2. Event Choreography**


The system supports two parallel execution flows based on the Interface's dual roles:

**A. Autonomous Scraping Flow**
1.  **Sensing:** The **Interface** completes a scheduled task, uploads any heavy payload to the **Store**, and publishes a `PerceptionGathered` event (containing the URI).
2.  **Contextualizing:** The **Controller** consumes `PerceptionGathered`, publishes a `ContextRequested` event, and waits for the `ContextProvided` event from **Memory**.
3.  **Delegating:** The **Controller** evaluates the Perception, decides on an action, and publishes a `CommandIssued` event.
4.  **Executing:** The **Actor** consumes `CommandIssued`, performs the work, and publishes an `ActionRequired` event (if external interaction is needed).
5.  **Recording:** The **Actor** publishes a `TaskCompleted` event. The **Memory** silently consumes this to log the operational record.

**B. User Chat Flow**
1.  **Receiving:** An authorized user sends a message. The Proxy Website forwards the payload to the **Interface**, which publishes a `UserPromptReceived` event (containing the text and the proxy's `user_id`).
2.  **Contextualizing:** The **Controller** consumes `UserPromptReceived`, publishes a `ContextRequested` event to fetch that specific user's chat history, and waits for the `ContextProvided` event from **Memory**.
3.  **Delegating:** The **Controller** evaluates the prompt and publishes a `CommandIssued` event.
4.  **Executing:** The **Actor** consumes the command, does internal processing, and publishes an `ActionRequired` event containing the text response targeted at the `user_id`, followed by a `TaskCompleted` event for logging.
5.  **Replying:** The **Interface** consumes `ActionRequired` and pushes the payload back to the Proxy Website.

**4.3. Security**
The local network operates on a "Zero Trust" model. The Event Broker must enforce Access Control Lists (ACLs). For example, the Interface is granted permission to *publish* to the Perception topic, but the Actor is not. Components authenticate with the Broker and Store using credentials provided by the Configurator at startup.

## 5. Fault Tolerance & Resilience

* **Fail-Fast & Orchestration:** If a component encounters an unrecoverable error, it must crash immediately. An external container orchestrator (like Docker) detects the crash and reboots it.
* **Guaranteed Delivery (At-Least-Once):** Because components use "Consumer Groups" to connect to the Event Broker, if a component crashes, the broker simply holds the messages in the queue. When the component restarts, it picks up exactly the next event in the stream. No data is lost.
* **Idempotency:** Because event delivery is typically "at-least-once" (meaning network blips might cause a message to be delivered twice), the internal logic of the Controller, Actor, and Memory must be designed idempotently to handle duplicate events gracefully.

## 6. Administration & inspector Data Flow

While operational data flows through the Event Broker, administrative oversight remains direct.
* **inspector APIs:** Every component must expose a lightweight, read-only internal HTTP API endpoint.
* **Aggregation:** The **Inspector** connects directly to these inspector APIs to query internal database health, scheduler status, and event consumer lag, presenting this to the authorized human operator.

## 7. Observability: Extensive Structured Logging

All components must implement strict, structured logging to trace asynchronous events across the distributed system.

* **Format:** Logs must be in a machine-readable structured format (e.g., JSON).
* **Standardized Schema:** Every log entry must include:
    * `timestamp`: ISO 8601 formatted time.
    * `component_name`: The emitting component.
    * `implementation_id`: The specific version or variant running.
    * `level`: Log severity (`INFO`, `WARN`, `ERROR`, `DEBUG`).
    * `correlation_id`: A unique identifier generated at the start of a workflow (e.g., when the Interface gathers a Perception or receives a User Prompt) and **injected into the headers of every subsequent event** to trace the entire lifecycle across all components.
    * `event`: A concise string describing the internal action (e.g., `event_consumed`, `payload_uploaded`).
    * `payload`: A nested object containing context-specific data.
    
