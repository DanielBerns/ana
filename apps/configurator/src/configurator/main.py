import os
import yaml
from fastapi import FastAPI, HTTPException

# Import shared logger (assuming configurator also uses it)
from shared.config import setup_logger

logger = setup_logger("configurator_component")

app = FastAPI(title="Ana Configurator Component")

def load_yaml(filepath: str) -> dict:
    """Helper function to load a YAML file."""
    if not os.path.exists(filepath):
        logger.warning("yaml_file_not_found", payload={"filepath": filepath})
        return {}

    try:
        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error("failed_to_load_yaml", payload={"filepath": filepath, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Invalid YAML in {filepath}")

def get_base_dir():
    # Helper to find the root of the project to construct absolute paths
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

@app.get("/config/{component_name}")
async def get_configuration(component_name: str):
    """
    Provides dynamic configuration by merging global settings with the component's decentralized YAML.
    """
    base_dir = get_base_dir()
    central_settings_path = os.path.join(base_dir, "apps/configurator/src/configurator/settings.yaml")

    # 1. Load the central settings
    central_settings = load_yaml(central_settings_path)
    globals_cfg = central_settings.get("global", {})

    # 2. Find the path to the component's local config
    component_paths = central_settings.get("component_configs", {})
    relative_component_path = component_paths.get(component_name)

    if not relative_component_path:
        # Fallback if no specific file is mapped, just return globals
        logger.info("configuration_served_globals_only", payload={"component": component_name})
        return globals_cfg

    # 3. Load the component's local settings
    absolute_component_path = os.path.join(base_dir, relative_component_path)
    component_cfg = load_yaml(absolute_component_path)

    # 4. Merge global variables and component-specific variables
    merged_config = {**globals_cfg, **component_cfg}

    logger.info("configuration_served", payload={"component": component_name})
    return merged_config

@app.get("/inspector")
async def inspector_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {"status": "healthy", "component": "configurator"}
