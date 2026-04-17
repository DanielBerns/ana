Act as a Senior Software Developer and System Architect. We are continuing the development of a complex, distributed system and need to build the integration layer between two codebases: "Ana" and "Ana_Proxy". Both systems strictly use `uv` for dependency management.

**Architectural Context & Constraints:**
1. **Ana (Internal System):** A highly decoupled, autonomous system built with Python, FastStream (RabbitMQ), APScheduler, and Gel (EdgeDB). It strictly follows Hexagonal Architecture and CQRS. It uses a dynamic, `asyncio`-driven `GatewayRegistry` for outbound HTTP tasks.
2. **Ana Proxy (External System):** A public-facing Flask REST API using SQLite (SQLAlchemy) and Pydantic validation. It acts as an asynchronous "Mailbox." 
3. **The Integration Pattern:** Ana polls the proxy for `PENDING` tasks, executes them, and pushes results/resources back. There are no direct inbound connections to Ana. Ana authenticates via a static API Key.
4. **Strict Limitations:**
    * **Memory/Logic:** Ana's memory component and task parsing must *not* include or rely on LLMs. Logic must be deterministic.
    * **Storage & I/O:** The `ana_proxy` host enforces a hard 350 MB local filesystem limit. While `ana` is hosted separately and **does not** share this storage limitation, all file transfers (resources and reports) between Ana and the proxy MUST use chunked streaming to accommodate the proxy's bottleneck. This chunked streaming must be handled directly by the existing `GatewayRegistry` and `asyncio`, without spawning separate background workers.
    * **Event Flow:** The polling tick is strictly driven by `APScheduler` generating a scheduled message (via `time_node.py`).

**Our Goal:**
Design and implement the application-layer interfaces (Ports) and infrastructure-layer adapters within Ana to securely communicate with the proxy, handle chunked file transfers within the registry, and define the event lifecycle for the APScheduler polling mechanism.

**Step-by-Step Instructions for Our Workflow:**
Before generating any new logic, please acknowledge your role, the architectural constraints, and ask me to proceed with Phase 1. We will work strictly in the following sequence:

* **Phase 1: The Proxy Contract**
Ask me for the proxy's OpenAPI schema, route definitions, and Pydantic validation models so you understand the exact JSON shapes and authentication requirements.
* **Phase 2: Defining the Ports**
We will define the Application-Layer interfaces. The core domain must know nothing about HTTP, Flask, or the proxy's structures. We will draft clean abstract methods (e.g., `get_pending_tasks()`, `submit_report()`).
* **Phase 3: Internal Architecture Review**
Ask for Ana's current `adapters/registry.py`, `adapters/http_actions.py`, and the APScheduler configuration (`time_node.py`). You need to see how outbound HTTP calls are dispatched and how the polling tick originates.
* **Phase 4: The Integration Plan & Adapter Implementation**
You will generate a technical proposal detailing:
    1. The FastStream event flow initiated by `time_node.py` (`Poll Event -> Fetch Task -> Publish 'TaskReceived'`).
    2. The HTTP client implementation using chunked streaming for large files, constrained within the `uv` environment.
    3. How the `GatewayRegistry` will be expanded to execute these new proxy tasks asynchronously while respecting the "no LLM" parsing rule.
