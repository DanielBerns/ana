import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI
from datetime import datetime, timezone

# SQLAlchemy 2.0 Async imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, DateTime, select
from faststream.rabbit.fastapi import RabbitRouter

# Import our shared data contracts and config utilities
from shared.events import TaskCompleted, ContextRequested, ContextProvided
from shared.config import setup_logger, fetch_dynamic_config

# --- Logging Setup ---
logger = setup_logger("memory_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("memory", logger)

# Extract strictly required connection URLs
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]
database_url = DYNAMIC_CONFIG.get("database_url")

if not database_url:
    raise RuntimeError("Configuration missing 'database_url'")

# Initialize the Router and Database Engine WITH the fetched URLs
router = RabbitRouter(rabbitmq_url)
engine = create_async_engine(database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# --- Database Setup (Driven Adapter) ---
Base = declarative_base()

class TaskRecord(Base):
    """SQLAlchemy ORM Model for storing TaskCompleted events."""
    __tablename__ = "operational_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id: Mapped[str] = mapped_column(String, index=True)
    task_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    result_summary: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ==========================================
# EVENT CONSUMERS & PRODUCERS
# ==========================================

@router.subscriber("task_results")
async def handle_task_completed(event: TaskCompleted):
    """
    Consumes TaskCompleted events silently to log operational records.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("task_completed_consumed", payload={"task_name": event.task_name, "status": event.status})

    # Save the record to PostgreSQL
    async with AsyncSessionLocal() as session:
        try:
            record = TaskRecord(
                correlation_id=event.correlation_id,
                task_name=event.task_name,
                status=event.status,
                result_summary=event.result_summary
            )
            session.add(record)
            await session.commit()
            log.info("record_saved_to_db")
        except Exception as e:
            await session.rollback()
            log.error("db_insert_failed", payload={"error": str(e)})


@router.subscriber("context_requests")
async def handle_context_requested(event: ContextRequested):
    """
    Consumes requests for history, queries the DB, and publishes the context back.
    """
    log = logger.bind(correlation_id=event.correlation_id)
    log.info("context_request_consumed", payload={"user_id": event.user_id, "query_reference": event.query_reference})

    history_data = []

    # Dynamically fetch the history limit from our configuration (default to 5 if missing)
    history_limit = DYNAMIC_CONFIG.get("history_limit", 5)

    async with AsyncSessionLocal() as session:
        try:
            # For this example, we fetch past tasks associated with this workflow/user
            stmt = select(TaskRecord).order_by(TaskRecord.timestamp.desc()).limit(history_limit)
            result = await session.execute(stmt)
            records = result.scalars().all()

            for r in records:
                history_data.append({
                    "task_name": r.task_name,
                    "status": r.status,
                    "summary": r.result_summary,
                    "timestamp": r.timestamp.isoformat()
                })
            log.info("db_queried_for_context", payload={"records_found": len(history_data), "limit_applied": history_limit})

        except Exception as e:
            log.error("db_query_failed", payload={"error": str(e)})

    # Publish the context back to the requested topic (usually "context_responses")
    response_event = ContextProvided(
        correlation_id=event.correlation_id,
        user_id=event.user_id,
        history=history_data
    )

    await router.broker.publish(response_event, queue=event.reply_to_topic)
    log.info("context_provided_published", payload={"reply_to": event.reply_to_topic})


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes DB tables and manages the broker connection."""

    # 1. Initialize Database Tables (In production, use Alembic migrations instead!)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_initialized")

    # 2. FastStream's lifespan_context handles the RabbitMQ connection automatically
    async with router.lifespan_context(app):
        logger.info("memory_startup_complete")

        yield # App is running

    # 3. Graceful shutdown of the database engine
    if engine:
        await engine.dispose()
        logger.info("database_engine_disposed")

# Initialize the FastAPI app and attach the FastStream router
app = FastAPI(lifespan=lifespan, title="Ana Memory Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "memory",
        "database_connected": engine is not None,
        "active_config": DYNAMIC_CONFIG
    }
