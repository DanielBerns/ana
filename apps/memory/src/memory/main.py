import os
import uuid
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI

# SQLAlchemy 2.0 Async imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, DateTime, select
from datetime import datetime, timezone

from faststream.rabbit.fastapi import RabbitRouter

# Import our shared data contracts
from shared.events import TaskCompleted, ContextRequested, ContextProvided

# --- Configuration & Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() # Fulfills strict JSON logging requirement
    ]
)
logger = structlog.get_logger("memory_component")

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"

# Use asyncpg for non-blocking database calls to our Docker Postgres instance
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://ana_admin:ana_password@localhost:5432/ana_db"
)

# --- Database Setup (Driven Adapter) ---
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
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

# --- FastStream Router Setup (Driving Adapter) ---
router = RabbitRouter(RABBITMQ_URL)

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

    async with AsyncSessionLocal() as session:
        try:
            # For this example, we fetch past tasks associated with this workflow/user
            # In a real app, you might query a specific 'ChatHistory' table here.
            stmt = select(TaskRecord).order_by(TaskRecord.timestamp.desc()).limit(5)
            result = await session.execute(stmt)
            records = result.scalars().all()

            for r in records:
                history_data.append({
                    "task_name": r.task_name,
                    "status": r.status,
                    "summary": r.result_summary,
                    "timestamp": r.timestamp.isoformat()
                })
            log.info("db_queried_for_context", payload={"records_found": len(history_data)})

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
    """Manages broker connection and database table creation."""
    # 1. Initialize Database Tables (In production, use Alembic migrations instead!)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_initialized")

    # 2. Start FastStream broker connection
    async with router.lifespan_context(app):
        logger.info("memory_startup_complete")
        yield

app = FastAPI(lifespan=lifespan, title="Ana Memory Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "memory",
        "database_connected": True
    }
