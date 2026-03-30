import os
import yaml
from typing import Any
from pathlib import Path
import httpx
import structlog

def setup_logger(component_name: str):
    """Initializes and returns a structured JSON logger for the component."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
        ]
    )
    return structlog.get_logger(component_name)

def load_yaml(filename: str) -> dict:
    """Helper function to load a YAML file."""
    filepath = Path(filename)
    if not filepath.exists():
        return {}
    try:
        with open(filepath, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Invalid YAML in {filepath}") from e

def save_yaml(filepath: Path, config: dict[str, Any]) -> None:
    # Write the new, potentially templated YAML to the instance folder
    try:
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        raise RuntimeError(f"Check {filepath}") from e

def fetch_dynamic_config(component_name: str) -> dict:
    """Fetches the configuration synchronously from the Configurator component."""
    # Use the component name to build the default URL
    default_url = f"http://localhost:8005/config/{component_name}"
    configurator_url = os.getenv("CONFIGURATOR_URL", default_url)

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(configurator_url)
            response.raise_for_status()
            config = response.json()
    except Exception as e:
        raise RuntimeError(f"Cannot start {component_name} without configuration from {configurator_url}") from e

    # Validate that the critical RabbitMQ URL is present
    test_0 = config.get("global", {})
    test_1 = test_0.get("rabbitmq_url", False)
    if not test_1:
        raise RuntimeError("Configuration missing 'rabbitmq_url'")

    return config
