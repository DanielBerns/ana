import os
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

def fetch_dynamic_config(component_name: str, logger=None) -> dict:
    """Fetches the configuration synchronously from the Configurator component."""
    # Use the component name to build the default URL
    default_url = f"http://localhost:8005/config/{component_name}"
    configurator_url = os.getenv("CONFIGURATOR_URL", default_url)

    if logger:
        logger.info("fetching_configuration", payload={"url": configurator_url})

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(configurator_url)
            response.raise_for_status()
            config = response.json()

        if logger:
            logger.info("config_fetched_successfully")

    except Exception as e:
        if logger:
            logger.error("configurator_unreachable", payload={"error": str(e)})
        raise RuntimeError(f"Cannot start {component_name} without configuration from {configurator_url}") from e

    # Validate that the critical RabbitMQ URL is present
    if not config.get("rabbitmq_url"):
        raise RuntimeError("Configuration missing 'rabbitmq_url'")

    return config
