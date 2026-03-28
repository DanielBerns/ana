import os
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from contextlib import asynccontextmanager

import aiofiles
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from faststream.rabbit.fastapi import RabbitRouter
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Shared Contracts
from shared.events import BaseEvent, PayloadStored, ModifyFileRetention, ConfigurationUpdated, SystemFatalError
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

# Domain & Infrastructure
from store.domain.models import Base, FileRecord
from store.infrastructure.storage import LocalStorageAdapter

logger = setup_logger("store_component")

# ==========================================
# BOOTSTRAP & INFRASTRUCTURE
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("store", logger)
rabbitmq_url = DYNAMIC_CONFIG["global"]["rabbitmq_url"]
database_url = DYNAMIC_CONFIG["global"]["database_url"]

engine = create_async_engine(database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

router = RabbitRouter(rabbitmq_url)

class StoreHost:
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = StoreHost(router)
storage = LocalStorageAdapter(base_dir=DYNAMIC_CONFIG.get("storage_dir", "/tmp/ana_storage"))

# ==========================================
# EVENT HANDLERS
# ==========================================
class RetentionHandler:
    """Listens for ModifyFileRetention events and updates the database."""
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("storage.retention_updates", self)

    async def handle(self, event: ModifyFileRetention) -> None:
        if not self.enabled: return
        log = logger.bind(correlation_id=event.correlation_id)

        async with AsyncSessionLocal() as session:
            # Calculate new expiration based on policy
            expires_at = None
            if event.new_policy == "ephemeral":
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            elif event.new_policy == "standard":
                expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            # 'preserved' remains None

            await session.execute(
                update(FileRecord)
                .where(FileRecord.hash_id == event.hash_id)
                .values(retention_policy=event.new_policy, expires_at=expires_at)
            )
            await session.commit()
            log.info("retention_policy_updated", payload={"hash_id": event.hash_id, "new_policy": event.new_policy})

# ==========================================
# GARBAGE COLLECTOR (Scheduled Task)
# ==========================================
async def collect_garbage():
    """Finds expired records, deletes physical files, and removes DB rows."""
    log = logger.bind(job="garbage_collector")
    try:
        async with AsyncSessionLocal() as session:
            # 1. Fast SQL query to find expired artifacts
            result = await session.execute(
                select(FileRecord).where(FileRecord.expires_at < datetime.now(timezone.utc))
            )
            expired_records = result.scalars().all()

            if not expired_records:
                return

            deleted_count = 0
            for record in expired_records:
                # 2. Physically delete from disk/S3
                success = await storage.delete(record.hash_id)
                if success or not os.path.exists(await storage.get_path(record.hash_id)):
                    # 3. Remove from database
                    await session.delete(record)
                    deleted_count += 1

            await session.commit()
            log.info("garbage_collection_complete", payload={"deleted_files": deleted_count})
    except Exception as e:
        log.error("garbage_collection_failed", payload={"error": str(e)})


# ==========================================
# APP LIFECYCLE & ROUTING
# ==========================================
retention_handler = RetentionHandler(DYNAMIC_CONFIG.get("event_handlers", {}).get("RetentionHandler", {}))
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await retention_handler.register(host)

    # Start Garbage Collector (runs every hour)
    scheduler.add_job(collect_garbage, 'interval', hours=1)
    scheduler.start()

    async with router.lifespan_context(app):
        logger.info("store_startup_complete")
        yield
        scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="Ana Store Component")
app.include_router(router)


# ==========================================
# HTTP ENDPOINTS (The Interface)
# ==========================================
@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    collection_id: Optional[str] = Form(None),
    retention_policy: str = Form("standard")
):
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)

    # 1. Stream to temporary file and calculate SHA-256 simultaneously
    temp_path = f"/tmp/{uuid.uuid4().hex}.tmp"
    sha256_hash = hashlib.sha256()
    size_bytes = 0

    async with aiofiles.open(temp_path, 'wb') as out_file:
        while chunk := await file.read(8192):
            sha256_hash.update(chunk)
            size_bytes += len(chunk)
            await out_file.write(chunk)

    hash_id = f"sha256-{sha256_hash.hexdigest()}"

    # 2. Hand off to the StorageAdapter (moves the temp file)
    await storage.put(temp_path, hash_id)

    # 3. Database Metadata Logic
    expires_at = None
    if retention_policy == "ephemeral":
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    elif retention_policy == "standard":
        expires_at = datetime.now(timezone.utc) + timedelta(days=DYNAMIC_CONFIG.get("ttl_days", 7))

    async with AsyncSessionLocal() as session:
        # Upsert logic (if hash exists, we don't need to insert again, just return it)
        existing = await session.execute(select(FileRecord).where(FileRecord.hash_id == hash_id))
        if not existing.scalars().first():
            new_record = FileRecord(
                hash_id=hash_id, original_filename=file.filename,
                mime_type=file.content_type or "application/octet-stream",
                size_bytes=size_bytes, collection_id=collection_id,
                retention_policy=retention_policy, expires_at=expires_at
            )
            session.add(new_record)
            await session.commit()

    # 4. Emit Event
    uri = f"{DYNAMIC_CONFIG.get('store_base_url', 'http://localhost:8001')}/files/{hash_id}"
    event = PayloadStored(
        correlation_id=correlation_id, hash_id=hash_id, uri=uri,
        mime_type=file.content_type, collection_id=collection_id, size_bytes=size_bytes
    )
    await host.publish(event, queue="payloads_stored")

    log.info("file_stored", payload={"hash_id": hash_id, "collection": collection_id})
    return {"hash_id": hash_id, "uri": uri, "status": "success"}


@app.get("/files/{hash_id}")
async def get_file(hash_id: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FileRecord).where(FileRecord.hash_id == hash_id))
        record = result.scalars().first()

        if not record:
            raise HTTPException(status_code=404, detail="File metadata not found")

        file_path = await storage.get_path(hash_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Physical file missing")

        return FileResponse(file_path, media_type=record.mime_type, filename=record.original_filename)

@app.get("/collections/{collection_id}")
async def get_collection(collection_id: str):
    """Allows the Archiver Actor to find all files in a specific roll-up sequence."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(FileRecord).where(FileRecord.collection_id == collection_id))
        records = result.scalars().all()
        return {
            "collection_id": collection_id,
            "count": len(records),
            "files": [{"hash_id": r.hash_id, "filename": r.original_filename} for r in records]
        }

@app.get("/inspector")
async def inspector_endpoint():
    return {"status": "healthy", "component": "store", "active_config": DYNAMIC_CONFIG}
