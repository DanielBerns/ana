Here is the updated `README.md` reflecting the new environment variable setup for Docker Compose and the Makefile targets. 

```markdown
# Ana: Autonomous Event-Driven Agent

Ana is an event-driven, microservice-based AI system built with Hexagonal Architecture. It autonomously scrapes web data, processes RSS feeds, archives artifacts, and features a conversational AI loop, all orchestrated through a RabbitMQ event bus and backed by PostgreSQL.

The system is designed for complete environment isolation. You can run multiple separate "instances" (e.g., `devel`, `testing`, `prod`) on the same machine, each with its own dedicated database, RabbitMQ virtual host, and configuration files.

## 🛠️ Prerequisites

To run Ana, you need the following tools installed on your system:
* **Python 3.11+**
* **[uv](https://github.com/astral-sh/uv)** (Python package and project manager)
* **Docker** and **Docker Compose**
* **Make** (for running Makefile commands)

---

## 🚀 Installation & Setup

**1. Clone the repository and sync dependencies:**
```bash
git clone <your-repo-url>
cd ana
make sync
```

**2. Set up Environment Variables:**
Before starting the infrastructure, you must generate a `.env` file containing your database and message broker credentials.
```bash
make create-env
```
*(This creates a default `.env` file in your directory. You can edit this file to change the default passwords if desired).*

**3. Start the Infrastructure (Docker):**
This spins up PostgreSQL and RabbitMQ in the background, validating that your `.env` file exists before starting.
```bash
make up
```

**4. Provision an Instance:**
Before starting the system, you must provision an isolated database and message queue for your specific instance (e.g., `devel`).
```bash
make provision INSTANCE=devel
```

---

## 🏃‍♂️ Running the System

Ana's microservices run independently. You will need to open a separate terminal tab/window for each component. 

*Note: The **Configurator** must be started first, as it generates and serves the YAML configuration files for the rest of the system.*

**Terminal 1: Configurator**
```bash
make run-configurator INSTANCE=devel
```
*(On its first run, this will create `~/ana/devel/` and copy all default configuration files there).*

**Terminal 2: Store**
```bash
make run-store INSTANCE=devel
```

**Terminal 3: Memory**
```bash
make run-memory INSTANCE=devel
```

**Terminal 4: Interface**
```bash
make run-interface INSTANCE=devel
```

**Terminal 5: Controller**
```bash
make run-controller INSTANCE=devel
```

**Terminal 6: Actor**
```bash
make run-actor INSTANCE=devel
```

**Terminal 7: Inspector (UI)**
```bash
make run-inspector INSTANCE=devel
```

---

## 📊 The Inspector Dashboard

Once everything is running, you can monitor the system, view saved HTML/XML artifacts, and browse the database via the Inspector web UI.

1. Open your browser and navigate to: `http://localhost:8006/dashboard`
2. **Login Credentials:**
   * **Username:** `admin`
   * **Password:** `admin`

*(If you are accessing it from another device on your local network, replace `localhost` with your machine's local IP address).*

---

## ⚙️ Configuration Management

Ana uses an "Instance-Based Configuration" model. Your active configuration files are **not** loaded from the Git repository. 

When you run `make run-configurator INSTANCE=devel`, the system creates a folder at:
`~/ana/devel/`

To change Ana's behavior (like adding new websites to scrape, changing the ETL intervals, or enabling/disabling rules), edit the YAML files located in that `~/ana/devel/` directory. The changes will be applied upon restarting the respective component.

---

## 🧹 Teardown & Reset

**To stop the infrastructure:**
```bash
make down
```

**To completely wipe all data (Factory Reset):**
If you want to permanently delete all databases, chat history, downloaded files, and RabbitMQ queues to start completely fresh:
```bash
docker compose down -v
```
*(After doing this, you will need to run `make up` and `make provision INSTANCE=devel` again).*
```
