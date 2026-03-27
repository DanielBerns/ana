Here is a complete `README.md` file tailored for the Ana system. It provides a clear overview of the architecture and step-by-step instructions for getting the entire distributed system running locally using the `uv` monorepo and Docker setup we built.

-----

# Ana System (v7.1)

Ana is a long-running, distributed, and asynchronous agent-based system built on an **Event-Driven Architecture (EDA)**. It is designed to autonomously scrape data, process user chat prompts via a proxy, and execute complex workflows across network-partitioned services.

## 🏗️ Architecture Highlights

  * **Event-Driven:** Components communicate asynchronously via RabbitMQ, ensuring guaranteed delivery and fail-fast resilience.
  * **Hexagonal Architecture:** Pure Python domain logic is strictly isolated from inbound/outbound network adapters.
  * **Claim Check Pattern:** Heavy payloads (like scraped media) are saved to a central Store via HTTP, while only lightweight URIs are passed through the event stream.
  * **Dynamic Configuration:** All components boot up stateless and fetch their configuration from a central Configurator server.

## 🧩 Components

The system consists of 7 custom Python microservices and 2 infrastructure services:

1.  **Configurator (Port 8005):** Centralized settings and security server.
2.  **Interface (Port 8000):** The sensory boundary. Handles autonomous scraping (cron) and inbound/outbound chat webhooks.
3.  **Store (Port 8001):** Blob storage for heavy payloads with an automated TTL garbage collector.
4.  **Controller (Port 8002):** The decision-making engine.
5.  **Actor (Port 8003):** The execution engine.
6.  **Memory (Port 8004):** PostgreSQL-backed storage for chat context and operational logging.
7.  **Inspector (Port 8006):** Centralized administrative dashboard.

-----

## 🚀 Prerequisites

Before running Ana, ensure you have the following installed on your machine:

  * **Python 3.11+**
  * **[uv](https://github.com/astral-sh/uv):** The lightning-fast Python package manager.
  * **Docker & Docker Compose:** For running RabbitMQ and PostgreSQL.
  * **Make:** For executing the simplified startup commands.

-----

## 🛠️ Setup & Installation

1.  **Clone the repository and navigate to the root directory:**

    ```bash
    cd ana
    ```

2.  **Sync the dependencies:**
    This command uses `uv` to resolve the monorepo workspace and install all dependencies into a unified virtual environment.

    ```bash
    make sync
    ```

3.  **Start the Infrastructure:**
    Spin up the RabbitMQ Event Broker and the PostgreSQL Database in the background.

    ```bash
    make up
    ```

    *(Note: You can view the RabbitMQ management dashboard at `http://localhost:15672` using `guest` / `guest`).*

-----

## 🏃‍♂️ Running the System

Because Ana is a distributed system, each component runs as its own non-blocking process. You will need to open **multiple terminal tabs** (one for each service).

**⚠️ IMPORTANT BOOT ORDER:** The Configurator *must* be started first, as all other components pause their startup to fetch their settings from it.

**Terminal 1:** Start the Configurator

```bash
make run-configurator
```

*Wait for the Configurator to show `configuration_served`, then start the rest in separate terminals:*

**Terminal 2:** Start the Blob Store

```bash
make run-store
```

**Terminal 3:** Start the Interface (Chat Bridge & Scraper)

```bash
make run-interface
```

**Terminal 4:** Start the Controller (Decision Engine)

```bash
make run-controller
```

**Terminal 5:** Start the Actor (Execution Engine)

```bash
make run-actor
```

**Terminal 6:** Start the Memory (Database logging)

```bash
make run-memory
```

**Terminal 7:** Start the Inspector (Admin Dashboard)

```bash
make run-inspector
```

-----

## 🎮 Interacting with Ana

### 1\. Trigger the Chat Flow

You can simulate an external proxy website sending a user message to Ana. Run this `curl` command in a new terminal:

```bash
curl -X POST http://localhost:8000/webhook/chat \
     -H "Content-Type: application/json" \
     -d '{"user_id": "user_123", "message": "Trigger the full system!"}'
```

*Watch your terminal logs\! You will see the event flow through the Interface -\> Controller -\> Memory -\> Actor -\> Interface -\> Memory, tracked perfectly via a unified `correlation_id`.*

### 2\. View the Admin Dashboard

The Inspector aggregates the health and state of every running component.

  * **URL:** [http://localhost:8006/dashboard](https://www.google.com/search?q=http://localhost:8006/dashboard)
  * **Username:** `admin`
  * **Password:** `supersecretpassword`

### 3\. Shutting Down

To gracefully stop the Python processes, press `Ctrl+C` in each terminal tab.
To spin down the Docker infrastructure and remove the containers, run:

```bash
make down
```

-----

## 📁 Project Structure

```text
ana/
├── pyproject.toml            # Root workspace config
├── uv.lock                   # Unified dependency lockfile
├── docker-compose.yml        # Infrastructure config
├── Makefile                  # Helper commands
├── packages/
│   └── shared/               # Pure Python domain models (Events)
└── apps/                     # Executable Microservices
    ├── configurator/
    ├── store/
    ├── interface/
    ├── controller/
    ├── actor/
    ├── memory/
    └── inspector/
```
