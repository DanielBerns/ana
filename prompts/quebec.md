### Phase 0: Project Initialization & Tooling
Starting from an empty repository, this phase establishes the foundation, dependency management, and automation.

* **Dependency Management:** Initialize the project using `uv init`. We will use `uv add` to manage dependencies like `faststream`, `edgedb`, `aiofiles`, `rocketry`, `pydantic`, and testing libraries (`pytest`, `pytest-asyncio`).
* **Makefile Creation:** Generate a `Makefile` to serve as the standard entry point for all developer commands. Targets will include:
    * `make install`: Syncs dependencies using `uv`.
    * `make db-init`: Runs EdgeDB schema migrations.
    * `make test`: Executes the test suite.
    * `make run`: Starts the FastStream broker and Rocketry scheduler.
    * `make format`: Runs linters and formatters (e.g., Ruff).
* **Project Structure:** Set up the Hexagonal directory structure (e.g., `src/domain`, `src/adapters`, `src/ports`, `src/agents`, `cli/`).

### Phase 1: Domain Core & Interfaces
Implementing the immutable contracts without infrastructure dependencies.

* **DTOs:** Define Pydantic models for `MessageHeader`, `BaseCommand`, `BaseEvent`, and specific events/commands (`ExecuteIONodeCommand`, `ResourceCreatedEvent`, etc.).
* **Knowledge Graph Tuples:** Implement the frozen, hashable Pydantic models for `SPOCTuple` and `EAVTTuple`.
* **Ports:** Define the `typing.Protocol` interfaces for `MessageBusPort`, `ResourceRepositoryPort`, and `KnowledgeGraphPort`.
* **Testing:** Unit tests for Pydantic serialization and hashability of the 4-tuples.

### Phase 2: Persistence & Storage Adapters
Building the interfaces to the local file system and the graph database.

* **Resource Repository (`aiofiles`):** Implement `ResourceRepositoryPort` to asynchronously save and fetch raw byte streams to the local disk, generating secure URIs for the metadata.
* **Knowledge Graph (EdgeDB):** Implement `KnowledgeGraphPort`. We will design the EdgeDB `.esdl` schema to natively handle SPOC and EAVT tuples. The adapter will handle the idempotent upsert operations and execute EdgeQL read queries.
* **Testing:** Integration tests using a local EdgeDB instance to verify idempotency and correct graph merging, alongside local temporary directories for testing `aiofiles` reads/writes.

### Phase 3: The Message Broker (FastStream)
Wiring up the reactive nervous system of the application.

* **Implementation:** Configure FastStream with the RabbitMQ backend. Define the Topic Exchanges and bind the Pydantic DTOs directly to the FastStream subscribers to leverage automatic deserialization and routing.
* **Resiliency:** Implement the explicit NACK mechanism (`requeue=False`) at the FastStream boundary so unexpected states immediately route messages to the Dead Letter Exchange and crash the specific node.
* **Testing:** Spin up a local RabbitMQ instance (via testcontainers or standard local dev setup) to verify FastStream routes messages to the correct functions based on routing keys.

### Phase 4: Boundary Agents (Scheduler & IO Nodes)
Implementing the components that interact with the outside world.

* **TimeNode (Rocketry):** Configure Rocketry to read a declarative YAML schedule. Rocketry's tasks will instantiate the `MessageBusPort` and push `ExecuteIONodeCommand`s onto the bus.
* **Inbound & Outbound IONodes:** Implement the strictly unidirectional nodes that react to FastStream triggers, interact with external APIs or local directories, use the `aiofiles` adapter to save payloads, and emit subsequent events.
* **Testing:** Mock external system responses and the bus to verify that triggers result in the correct sequence of saves and event emissions.

### Phase 5: Domain Agents (Processors, Reasoners, Reporters)
The pure domain logic that parses, deduces, and reports.

* **Processors:** Subscribe to `ResourceCreatedEvent` via FastStream, parse raw data, write `Tuple4` objects via the EdgeDB adapter, and emit `KnowledgeUpdatedEvent`.
* **Reasoners:** Deterministic rule-based engines that subscribe to `KnowledgeUpdatedEvent`. They will execute EdgeQL queries to pull sub-graphs, run logical deductions without relying on LLMs, push new tuples back to EdgeDB, and emit downstream events.
* **Reporters:** Subscribe to knowledge updates, construct final reports, save them via the `aiofiles` adapter, and emit `ReportCreatedEvent`.
* **Testing:** In-memory mocks for the ports to ensure the deterministic logic of Processors and Reasoners correctly translates raw data into the expected tuples.

### Phase 6: CLI & Admin Tools
Developing the offline administrative suite to manage Ana's lifecycle and configuration.

* **Implementation:** Use a library like `Typer` or `argparse` to create a command-line interface under a `scripts/` or `cli/` directory.
* **Commands:**
    * `ana-cli init`: Bootstraps the local environment, creating necessary directory structures for `aiofiles` and applying initial EdgeDB migrations.
    * `ana-cli reset`: Safely truncates the EdgeDB graph and clears the local file repository for a clean slate.
    * `ana-cli backup`: Dumps the EdgeDB schema/data and archives the local file repository into a compressed tarball.
    * `ana-cli config generate`: Scaffolds default YAML configuration files (for Rocketry schedules, node configurations).
    * `ana-cli config update`: Validates and applies updates to existing YAML configurations.
* **Testing:** Unit tests verifying that the CLI correctly invokes the underlying system commands and database connections without needing the FastStream broker to be online.

---

