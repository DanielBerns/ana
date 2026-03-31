import os
import yaml
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from shared.config import setup_logger, load_yaml, save_yaml

logger = setup_logger("configurator_component")

INSTANCE_NAME = os.environ.get("ANA_INSTANCE", "devel")
BASE_DIR = Path.home() / "ana" / INSTANCE_NAME

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
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Bootstrapping instance '{INSTANCE_NAME}' at {BASE_DIR}")

    for component, original_path in DEFAULT_FILES.items():
        target_path = BASE_DIR / f"{component}.yaml"

        config_data = load_yaml(original_path)
        if not target_path.exists():
            logger.info(f"Seeding {target_path.name} from repository...")
            if component == "settings":
                global_config = config_data.get("global", {})

                # Template RabbitMQ
                rmq_url = global_config.get("rabbitmq_url", "amqp://guest:guest@localhost:5672/")
                if not rmq_url.endswith("/"):
                    rmq_url += "/"
                config_data["global"]["rabbitmq_url"] = f"{rmq_url}{INSTANCE_NAME}"

                # Template PostgreSQL safely (only modify the end of the string)
                db_url = global_config.get("database_url", "postgresql+asyncpg://ana_admin:ana_password@localhost:5432/ana")
                if db_url.endswith("/ana"):
                    # Slice off the last 4 characters ("/ana") and append the new name
                    config_data["global"]["database_url"] = db_url[:-4] + f"/ana_{INSTANCE_NAME}"
                else:
                    config_data["global"]["database_url"] = f"{db_url}_{INSTANCE_NAME}"
            save_yaml(target_path, config_data)

# FIX: Added deep merge helper
def deep_merge(dict1: dict, dict2: dict) -> dict:
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_instance()
    yield

app = FastAPI(title="Ana Configurator Component", lifespan=lifespan)

@app.get("/config")
async def get_global_settings():
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
    global_settings_path = BASE_DIR / "settings.yaml"
    component_settings_path = BASE_DIR / f"{component}.yaml"

    if not global_settings_path.exists():
        raise HTTPException(status_code=404, detail="Global settings not found.")
    if not component_settings_path.exists():
        raise HTTPException(status_code=404, detail=f"{component} settings not found.")

    global_settings = load_yaml(global_settings_path)
    component_settings = load_yaml(component_settings_path)

    # FIX: Uses deep_merge instead of shallow {**global_settings, **component_settings}
    config = deep_merge(global_settings, component_settings)
    logger.info("config_served", payload={"component": component})
    return config

@app.get("/inspector")
async def inspector_endpoint():
    return {"status": "healthy", "component": "configurator"}
