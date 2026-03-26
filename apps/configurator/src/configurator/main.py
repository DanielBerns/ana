import os
import yaml
import structlog
from fastapi import FastAPI, HTTPException

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() #
    ]
)
logger = structlog.get_logger("configurator_component")

app = FastAPI(title="Ana Configurator Component")

def load_settings():
    """Loads the YAML file containing the system configuration."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(base_dir, "settings.yaml")
    try:
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error("failed_to_load_settings", error=str(e))
        return {}

@app.get("/config/{component_name}")
async def get_configuration(component_name: str):
    """
    Provides dynamic configuration for a specific component.
    Merges global settings (like DB and Broker URLs) with component-specific ones.
    """
    settings = load_settings()
    globals_cfg = settings.get("global", {})
    component_cfg = settings.get("components", {}).get(component_name)

    if component_cfg is None:
        raise HTTPException(status_code=404, detail=f"Configuration for '{component_name}' not found.")

    # Merge global variables and component-specific variables into one dictionary
    merged_config = {**globals_cfg, **component_cfg}

    logger.info("configuration_served", component=component_name)
    return merged_config

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {"status": "healthy", "component": "configurator"}
