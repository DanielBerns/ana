import os
import time
import uuid
import structlog
import aiofiles
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# --- Configuration & Logging Setup ---
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer() #
    ]
)
logger = structlog.get_logger("store_component")

# Define where files will be saved. In Docker, this maps to the named volume.
STORAGE_DIR = os.getenv("STORAGE_DIR", "/tmp/ana_store")
os.makedirs(STORAGE_DIR, exist_ok=True)

# TTL Configuration: Delete files older than 7 days (604800 seconds)
TTL_SECONDS = int(os.getenv("TTL_SECONDS", 604800))

# --- Scheduler Setup ---
scheduler = AsyncIOScheduler()

async def enforce_ttl_policy():
    """
    Garbage collection job. Scans the storage directory and removes files
    that have exceeded the Time-To-Live (TTL).
    """
    log = logger.bind(event="ttl_garbage_collection")
    log.info("starting_cleanup_scan")

    current_time = time.time()
    deleted_count = 0

    try:
        for filename in os.listdir(STORAGE_DIR):
            file_path = os.path.join(STORAGE_DIR, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getctime(file_path)
                if file_age > TTL_SECONDS:
                    os.remove(file_path)
                    deleted_count += 1

        log.info("cleanup_finished", payload={"deleted_files": deleted_count})
    except Exception as e:
        log.error("cleanup_failed", payload={"error": str(e)})

# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run the TTL cleanup every hour
    scheduler.add_job(enforce_ttl_policy, 'interval', hours=1)
    scheduler.start()
    logger.info("store_startup_complete")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan, title="Ana Store Component")

# ==========================================
# RESOURCE API (CRUD)
# ==========================================

@app.post("/files")
async def upload_file(file: UploadFile = File(...)):
    """Receives a heavy payload and returns a Claim Check URI."""
    correlation_id = str(uuid.uuid4())
    log = logger.bind(correlation_id=correlation_id)

    # Generate a unique filename to prevent collisions
    safe_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(STORAGE_DIR, safe_filename)

    try:
        # Save the file asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await out_file.write(content)

        # Generate the URI that other components will use
        # In a real setup, you'd use the actual domain/IP. For now, localhost/Docker service name.
        uri = f"http://localhost:8001/files/{safe_filename}"

        log.info("file_uploaded", payload={"filename": file.filename, "size_bytes": os.path.getsize(file_path)})
        return {"uri": uri, "filename": safe_filename}

    except Exception as e:
        log.error("upload_failed", payload={"error": str(e)})
        raise HTTPException(status_code=500, detail="Could not save file")

@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serves a previously uploaded file."""
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "files_stored": len(os.listdir(STORAGE_DIR)) if os.path.exists(STORAGE_DIR) else 0
    }
