This is a phenomenal, production-grade specification. The Ana v7.1 system is incredibly well-thought-out, particularly the shift to an Event-Driven Architecture (EDA) and the use of the "Claim Check" pattern to keep the event streams lightweight. 

Since you are aiming for a working system that prioritizes ease of development and maintainability over extreme high-performance scaling, we can select a modern, developer-friendly Python stack that perfectly aligns with the Hexagonal Architecture mandate.

Here is the recommended technology stack and implementation strategy to bring Ana to life.

### 1. The Recommended Tech Stack

* **Dependency Management & Tooling:** Use `uv` for lightning-fast project and virtual environment management.
* **Web Framework (Diagnostic APIs, Store, Configurator):** `FastAPI`. It is asynchronous, self-documenting, and incredibly fast to develop with.
* **Data Validation & Domain Models:** `Pydantic`. This will define your core domain entities and ensure your event payloads are strictly typed.
* **Database & Migrations:** `SQLAlchemy` 2.0 (using its async engine) paired with `Alembic` for database migrations. Each component that requires state (Memory, Controller, Actor) will have its own isolated SQLite or PostgreSQL database.
* **Event Framework:** **`FastStream`**. This is a highly recommended Python library specifically designed for event-driven microservices. It wraps message brokers with a syntax that looks exactly like FastAPI, making it effortless to consume and produce events using Pydantic schemas.
* **Event Broker:** **RabbitMQ** or **Redis Streams**. For a low-complexity setup, running RabbitMQ via Docker provides robust "at-least-once" delivery and consumer groups right out of the box.
* **Task Scheduling (Interface):** `APScheduler` or `Rocketry` running inside the Interface component to handle the autonomous `cron`-based scraping.
* **Orchestration:** `Docker` and `Docker Compose` to spin up the broker, databases, and the individual Python microservices simultaneously.

### 2. Mapping to Hexagonal Architecture

The specification mandates Hexagonal Architecture (Ports and Adapters). Here is how the recommended stack fits into that pattern:

* **Domain Core:** Pure Python classes and `Pydantic` models representing your business logic (e.g., `Perception`, `Command`, `Action`). Absolutely no FastAPI or SQLAlchemy code lives here.
* **Inbound Adapters (Driving Ports):** * `FastStream` routers that listen to the Event Broker and trigger domain logic.
    * `FastAPI` endpoints serving as the Diagnostic APIs or the Proxy Website webhook receivers.
* **Outbound Adapters (Driven Ports):** * `SQLAlchemy` repository classes that save and retrieve data from the internal databases.
    * `FastStream` publisher functions that broadcast events back to the broker.

### 3. Component Implementation Strategy

Here is a pragmatic approach to building the 8 core components for a functional, non-hyper-scaled environment:

* **1. Event Broker:** Don't build this. Use the official RabbitMQ Docker image.
* **2. Configurator:** A lightweight FastAPI service. For now, it can simply read a central `config.yaml` file and serve it via a `/config` REST endpoint to the other components on boot.
* **3. Store:** A simple FastAPI service that accepts `POST` file uploads, saves them to a mounted local Docker volume, and returns a URI (e.g., `http://store:8000/files/12345.pdf`). You can implement a background task using `APScheduler` to enforce the Time-To-Live (TTL) garbage collection.
* **4. Memory:** A FastStream consumer that listens for `TaskCompleted` events and an SQLAlchemy backend to store them. It will also listen for `ContextRequested` events and reply with the history.
* **5. Controller & 6. Actor:** The brains and hands. Built with FastStream to listen to their respective topics, process the data through your domain logic, and publish the subsequent events.
* **7. Interface:** This will be a dual-purpose FastAPI/FastStream app. `APScheduler` will run background tasks for scraping. FastAPI endpoints will act as the Chat Bridge to receive webhooks from your Proxy Website. FastStream will publish the resulting data to the broker.
* **8. Inspector:** A lightweight frontend (using basic HTML/JS or a simple framework like Streamlit) that makes HTTP GET requests to the Diagnostic APIs of the other containers.

### 4. Structured Logging Implementation

To meet the extensive structured logging requirement, you should configure Python's native `logging` module to output JSON. 

You can use a library like `structlog`. It allows you to easily bind the `correlation_id`, `component_name`, and `event` to every log statement natively, ensuring uniform machine-readable JSON across all components. 

### Next Steps: Where to Start?

When building distributed systems, the "Big Bang" approach usually leads to frustration. I recommend this sequence to get off the ground:

1.  **Define the Schema Contract:** Create a shared Python package (or just a shared folder if using a monorepo) containing the Pydantic models for every event (e.g., `PerceptionGathered`, `CommandIssued`). This is your system's source of truth.
2.  **Infrastructure Foundation:** Create a `docker-compose.yml` file that spins up RabbitMQ and an empty PostgreSQL container.
3.  **Build the Skeleton:** Create barebones FastStream apps for the Controller, Actor, Interface, and Memory that just print to the console when they receive an event.
4.  **Test the Plumbing:** Manually inject a `PerceptionGathered` event into RabbitMQ and watch it flow through the system.

Would you like to start by drafting the Pydantic schemas for the core events, or would you prefer to set up the `uv` monorepo structure and the `docker-compose.yml` file?
