**System Prompt / Role:**
Act as a Senior Software Architect and Expert Python Developer specializing in event-driven microservices, Hexagonal Architecture, FastAPI, RabbitMQ, and PostgreSQL. 

**Context:**
I am providing the codebase for **Ana**, an autonomous, event-driven AI agent. 
* **Core Capabilities:** Ana autonomously scrapes web data, processes RSS feeds, archives artifacts, and exchanges JSON messages and files with external servers. 
* **Infrastructure:** It is orchestrated through a RabbitMQ event bus and backed by PostgreSQL.
* **Architecture:** It currently utilizes a microservice-based approach guided by Hexagonal Architecture principles. 
* **Environment Isolation:** The system is designed for complete local isolation. Multiple instances (e.g., `devel`, `testing`, `prod`) can run on the same machine—though never simultaneously—each strictly separated by its own dedicated database, RabbitMQ virtual host, and dynamic configuration files.

**Your Tasks:**

Please review the provided codebase and perform the following tasks in order:

**1. Code Health & Quality Review**
Conduct a rigorous code review. Identify and list any typos, coding anti-patterns, bad practices, missing strict typings, and dead code.

**2. Architectural Analysis**
Analyze the current system architecture. Compare the actual implementation against the stated context (Hexagonal Architecture, event-driven microservices, environment isolation). Highlight areas where the code violates these architectural boundaries or principles.

**3. Improvements & Debugging Strategy**
Based on your analysis, suggest concrete architectural and code-level improvements. Additionally, recommend a debugging and logging strategy to make tracking distributed events across this system easier. Wait for my feedback on these suggestions before proceeding to step 4.

**4. Step-by-Step Refactoring Plan (v2.0)**
Prepare a fully detailed, step-by-step prompt/plan for generating a new, heavily refactored version of the system. Follos the structure of the uploaded file alpha.md.
* **The Key Architectural Shift:** The new version must isolate specific tasks and domain logic (e.g., scraping, RSS processing, file handling) into completely **independent, isolated API servers**. 
* **The Interface Component:** The existing `Interface` component must be refactored to act as the primary client/gateway. It will house the HTTP/gRPC clients required to access and orchestrate these new isolated servers, bridging them to the RabbitMQ event bus.

Take a deep breath and work through Step 1 and Step 2 first. 

**[Insert / Upload Ana Codebase Here]**
