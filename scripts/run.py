import asyncio
import logging
from pathlib import Path
import structlog

from ana.application import app, message_bus
from ana.agents.time_node import scheduler_app, load_actions_from_config


# 1. Configure structlog for beautiful, human-readable console output
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # Merges contextvars into every log
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),  # Formats to screen
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("ana.runner")


async def main():
    logger.info("Initializing Ana System...", component="system")

    # 1. Load scheduled tasks into the scheduler memory
    scheduler_config_file = Path("config") / "scheduler.yaml"
    load_actions_from_config(message_bus, config_file=scheduler_config_file)
    logger.info("Scheduler tasks loaded.", config_file=str(scheduler_config_file))

    # 2. Hook the scheduler startup to FastStream's lifecycle
    # This ensures it ONLY starts after the broker is connected
    @app.on_startup
    async def start_background_tasks():
        scheduler_app.start()
        logger.info("APScheduler started natively within FastStream lifecycle.")

    logger.info("Ana is now ALIVE. Listening for events and schedule ticks...")

    # 3. Run the FastStream consumer (This establishes the connection)
    try:
        await app.run()
    except asyncio.CancelledError:
        logger.info("Shutting down Ana System gracefully...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
