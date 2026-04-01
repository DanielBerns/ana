import logging
import structlog
from contextvars import ContextVar
from typing import Any

# Global context variable for the correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="system_init")

def inject_correlation_id(logger: Any, method_name: str, event_dict: dict) -> dict:
    """Structlog processor to inject the correlation_id from ContextVars."""
    event_dict["correlation_id"] = correlation_id_var.get()
    return event_dict

def setup_logger(component_name: str) -> structlog.BoundLogger:
    """Configures structured JSON logging for a component."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            inject_correlation_id,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logger = logging.getLogger(component_name)
    logger.setLevel(logging.INFO)

    # Ensure standard logging outputs as JSON as well
    handler = logging.StreamHandler()
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return structlog.get_logger(component_name)
