import os
import asyncio
from alembic.config import Config
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from shared.logger import setup_logger

logger = setup_logger("memory.infrastructure")

# Standard PostgreSQL connection strings
# When running locally via 'uv run', it uses localhost. When in Docker, it uses the container name.
DB_USER = os.getenv("POSTGRES_USER", "ana_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "ana_password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "ana_db")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db_session():
    """Dependency injector for database sessions."""
    async with AsyncSessionLocal() as session:
        yield session

async def initialize_storage():
    """Runs database migrations to ensure schema is up to date."""
    logger.info("running_database_migrations")

    # Point Alembic to the config file
    alembic_cfg = Config("./apps/core/memory/alembic.ini")

    # Run the migration synchronously in a thread to avoid blocking the event loop
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    logger.info("database_migrations_complete")

async def close_storage():
    """Cleanly closes underlying connection pools."""
    logger.info("closing_database_connections")
    await engine.dispose()
