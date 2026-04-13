### The Prompt for the New Chat

**System Integration: Ana Core to Ana Proxy**

Act as a Senior Software Developer. We are integrating "Ana", an internal autonomous, event-driven agent (Python, Hexagonal Architecture, RabbitMQ/FastStream, and Gel - previously known as EdgeDB -), with "ana_proxy", a public-facing Flask/SQLite REST API.

**Architectural Context & Constraints:**
* **The Pattern:** `ana_proxy` is a strict polling mailbox. Humans enqueue tasks; Ana polls for `PENDING` tasks and pushes results/resources back. There are no webhooks or direct inbound connections to Ana.
* **Security & I/O:** Ana authenticates to the proxy via a static API Key. The proxy enforces a strict 350 MB local filesystem limit, meaning all file transfers (resources and reports) must be handled via chunked streaming.
* **Internal Constraints:** Ana's memory component design currently must *not* include or rely on LLMs. 

**Our Goal:** > Design and implement the infrastructure-layer adapters within Ana to communicate with the proxy, and define the event lifecycle for the polling mechanism. 

**Next Step:** > I will provide the proxy's API specification/routes and Ana's current application-layer ports. Please acknowledge this context, and then we will begin the codebase review step-by-step.

***

### Step-by-Step Codebase Review Instructions

Once the new chat is initialized and you have pasted the prompt, follow this sequence to review and build the integration. This ensures we don't violate your architectural boundaries.

**Step 1: Interface Definition (The Ports)**
* **Action:** Share Ana's application-layer interfaces (the Ports) that dictate what the core domain needs from the outside world.
* **Review:** We must ensure the core domain knows *nothing* about HTTP, Flask, or the proxy's specific JSON structures. We will define clean abstract methods like `get_pending_tasks()` and `submit_intelligence_report()`.

**Step 2: The Infrastructure Adapter (The HTTP Client)**
* **Action:** Share or draft the implementation of the proxy client.
* **Review:** Verify that the `uv` dependency management keeps libraries like `httpx` or `requests` strictly confined to this adapter module. We will review the payload construction, API key header injection, and ensure chunked streaming is utilized for file downloads/uploads to align with the proxy's 350 MB limit constraint. 

**Step 3: The Polling & Event Bus Integration**
* **Action:** Review how the polling mechanism interacts with RabbitMQ/FastStream.
* **Review:** Since we are using an event-driven setup, we need to decide if polling is driven by a scheduled message (e.g., a "tick" event on the queue) or a dedicated async worker. We will review the event flow: `Poll Event -> Fetch Task -> Publish 'TaskReceived' Event to internal bus`.

**Step 4: State & Memory Alignment**
* **Action:** Review the logic that handles a completed task and updates Ana's internal state.
* **Review:** Ensure that the parsing of task parameters and the formulation of the final report (`ReportMetadataSchema`) strictly adhere to the "no LLM" constraint in the memory loop. The integration must rely on deterministic logic and structured data mapping at this stage.


