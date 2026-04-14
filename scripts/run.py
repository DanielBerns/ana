# scripts/run.py
import asyncio
import logging

from ana.application import app, message_bus
from ana.agents.time_node import scheduler_app, load_actions_from_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("ana.runner")

async def main():
    logger.info("Initializing Ana System...")

    # 1. Load the scheduled tasks, injecting the live message bus
    load_actions_from_config(message_bus, config_path="config/scheduler.yml")
    logger.info("Scheduler tasks loaded.")

    # 2. Start the APScheduler in the background of the current event loop
    scheduler_app.start()

    logger.info("Ana is now ALIVE. Listening for events and schedule ticks...")

    # 3. Run the FastStream consumer (this blocks and keeps the application alive)
    try:
        await app.run()
    except asyncio.CancelledError:
        logger.info("Shutting down Ana System gracefully...")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
