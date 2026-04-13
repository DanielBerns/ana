# Ana: Autonomous Event-Driven System

Ana is a decoupled, event-driven intelligent system built using **Hexagonal Architecture** and the **CQRS** (Command Query Responsibility Segregation) pattern. 

The system relies on a dual-runner execution model:
1. **FastStream & RabbitMQ:** Handles the asynchronous message bus, routing events and commands between boundary agents and domain processors.
2. **APScheduler:** A background tick engine that dynamically executes time-based commands configured via YAML.
3. **Gel (EdgeDB) & Local Storage:** Manages the immutable Knowledge Graph and raw file persistence.

---

## Prerequisites

Before installing Ana, ensure you have the following system dependencies installed:

* **Python 3.14+** * **[uv](https://github.com/astral-sh/uv):** The blazing-fast Python package installer and resolver.
* **[Podman](https://podman.io/):** For running the daemonless, rootless RabbitMQ broker.
* **[Gel CLI](https://www.geldata.com/):** For managing the Knowledge Graph database.
* **Make:** For executing the automation targets.

---

## Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd ana
   ```

2. **Install Python dependencies:**
   Use `uv` to create the virtual environment and install the required packages.
   ```bash
   uv venv
   uv sync
   ```

---

## Initialization & Configuration

Ana includes a built-in Typer CLI for offline administration and bootstrapping.

1. **Initialize the Database and Local Storage:**
   This command creates the local storage directories and applies the Gel database migrations.
   ```bash
   make cli ARGS="init"
   ```

2. **Generate the Default Configuration:**
   This scaffolds the default `scheduler.yml` file used by the APScheduler `TimeNode`.
   ```bash
   make cli ARGS="config generate"
   ```

3. **Verify Configuration:**
   Validate that your YAML configuration strictly matches the internal Pydantic models.
   ```bash
   make cli ARGS="config validate"
   ```

---

## Running Ana

To bring Ana to life, you must start the message broker and then boot the dual-runner application.

### 1. Start the RabbitMQ Broker
Spin up the RabbitMQ container in the background using Podman.
```bash
make rabbit-up
```
*(The management UI will be available at `http://localhost:15672` with credentials `guest`/`guest`)*.

### 2. Boot the System
Start the main application. This will attach FastStream to the message bus, set up the topic exchanges, and start the APScheduler tick loop.
```bash
make run
```

### 3. Graceful Shutdown
* Stop Ana by pressing `Ctrl+C` in the terminal running the application.
* Spin down the RabbitMQ container:
  ```bash
  make rabbit-down
  ```

---

## Testing

Ana is heavily tested using `pytest` across unit, integration, and End-to-End (E2E) boundaries. The test suite uses an in-memory fake Knowledge Graph and a mock FastStream broker to ensure deterministic, rapid execution.

To run the complete 13-test suite:
```bash
make test
```

---

## System Administration (Offline CLI)

You can manage Ana's state safely while the system is offline using the provided CLI tools. 

**View all available commands:**
```bash
make cli ARGS="--help"
```

**Back up the system:**
Zips the local file storage and executes a Gel database dump to the `/backups` directory.
```bash
make cli ARGS="backup"
```

**Wipe the system (Caution):**
Truncates the Gel Knowledge Graph and safely wipes the local repository directory.
```bash
make cli ARGS="reset"
```
