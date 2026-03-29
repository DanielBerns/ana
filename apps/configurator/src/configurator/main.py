import os
import yaml
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("configurator")

# 1. Path Resolution via Environment Variable
INSTANCE_NAME = os.environ.get("ANA_INSTANCE", "devel")
BASE_DIR = Path.home() / "ana" / INSTANCE_NAME

# 2. Seed Mapping (Mapping API names to their repository source files)
REPO_ROOT = Path.cwd()
DEFAULT_FILES = {
    "settings": REPO_ROOT / "apps/configurator/src/configurator/settings.yaml",
    "interface": REPO_ROOT / "apps/interface/src/interface/config.yaml",
    "store": REPO_ROOT / "apps/store/src/store/config.yaml",
    "controller": REPO_ROOT / "apps/controller/src/controller/config.yaml",
    "actor": REPO_ROOT / "apps/actor/src/actor/config.yaml",
    "memory": REPO_ROOT / "apps/memory/src/memory/config.yaml",
    "inspector": REPO_ROOT / "apps/inspector/src/inspector/config.yaml"
}

def bootstrap_instance():
    """Ensures the instance directory exists and seeds it with default configs."""
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Bootstrapping instance '{INSTANCE_NAME}' at {BASE_DIR}")

    for component, original_path in DEFAULT_FILES.items():
        target_path = BASE_DIR / f"{component}.yaml"

        if not target_path.exists():
            logger.info(f"Seeding {target_path.name} from repository...")

            if not original_path.exists():
                logger.warning(f"Original repo file not found at {original_path}. Skipping.")
                continue

            # Read the original YAML
            with open(original_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}

            # Intelligent URL Templating for global settings
            if component == "settings":
                # Template RabbitMQ Virtual Host (e.g. amqp://guest:guest@localhost:5672/devel)
                rmq_url = config_data.get("rabbitmq_url", "amqp://guest:guest@localhost:5672/")
                if not rmq_url.endswith("/"):
                    rmq_url += "/"
                config_data["rabbitmq_url"] = f"{rmq_url}{INSTANCE_NAME}"

                # Template PostgreSQL Database Name (e.g. postgresql+asyncpg://admin:admin@localhost:5432/ana_devel)
                db_url = config_data.get("database_url", "postgresql+asyncpg://admin:admin@localhost:5432/ana")
                if db_url.endswith("/ana"):
                    config_data["database_url"] = db_url.replace("/ana", f"/ana_{INSTANCE_NAME}")
                else:
                    config_data["database_url"] = f"{db_url}_{INSTANCE_NAME}"

            # Write the new, potentially templated YAML to the instance folder
            with open(target_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_instance()
    yield

app = FastAPI(title="Ana Configurator Component", lifespan=lifespan)

@app.get("/config")
async def get_global_settings():
    """Serves the global settings from the instance directory."""
    file_path = BASE_DIR / "settings.yaml"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Global settings not found in instance folder.")

    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error parsing settings file")

@app.get("/config/{component}")
async def get_config(component: str):
    """Serves a specific component's configuration from the instance directory."""
    file_path = BASE_DIR / f"{component}.yaml"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Configuration for {component} not found in instance folder.")

    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error parsing configuration file")
