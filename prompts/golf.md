> **Act as an Expert Python Software Architect and QA Engineer.**
> 
> I am developing "Ana," an advanced, event-driven, neurosymbolic AI system built on a strict Hexagonal Architecture. The system is functional end-to-end, but I need your help to carefully review the codebase, identify hidden bugs or race conditions, and develop a comprehensive suite of testing scripts.
> 
> **System Architecture & Tech Stack:**
> * **Frameworks:** Python 3.12+, `uv` for dependency management, FastStream with RabbitMQ for event-routing, and FastAPI for the external gateway.
> * **Microservices:**
>     1.  `core-interface`: A webhook gateway receiving user prompts.
>     2.  `core-controller`: The central orchestrator utilizing a pure Python `SymbolicRuleEngine`.
>     3.  `core-memory`: A 4-dimensional (Subject, Predicate, Object, Graph) Quad-Store Knowledge Graph running on PostgreSQL, accessed via SQLAlchemy (`asyncpg`) and managed by Alembic.
>     4.  `core-actor`: A deterministic NLP engine using `scikit-learn` (TF-IDF) for text classification and keyword extraction.
>     5.  `edge-etl`: A dynamic factory using the Strategy Pattern to execute pipelines (Extractors: HTTP, Selenium, FileSystem; Transformers: DOM, Regex; Loaders: YAML, CSV).
>     6.  `shared`: A library containing Pydantic `BaseEvent` models and a `RabbitMQAdapter`.
> * **Infrastructure:** Orchestrated via Docker Compose with a `Makefile` for lifecycle management (`make init`, `make up`, `make test`).
> 
> **Our Goals for this Session:**
> 1.  **Code Review & Debugging:** I will provide snippets of my current microservices. I need you to look for async deadlocks, Pydantic validation edge-cases, RabbitMQ consumer misconfigurations, and unhandled exceptions.
> 2.  **Unit Testing:** Develop `pytest` scripts for the isolated domain logic (e.g., the Rule Engine, the NLP Extractor, and the ETL pipeline strategies) mocking out all infrastructure.
> 3.  **Integration Testing:** Develop scripts to test the FastStream RabbitMQ routing and the SQLAlchemy async repository (Quad-Store assertions).
> 4.  **E2E Testing:** Expand my basic `test_e2e.py` script into a robust suite that publishes specific RabbitMQ messages and listens for the expected cascade of neurosymbolic events.
> 
> If you understand the architecture and are ready to begin, please reply with "Acknowledged," outline your recommended strategy for tackling these tests, and tell me which files you would like me to share first.

