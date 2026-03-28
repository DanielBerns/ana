import os
import time
import uuid
import aiofiles
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import our shared config utilities
from shared.config import setup_logger, fetch_dynamic_config

# --- Logging Setup ---
logger = setup_logger("store_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("store", logger)
storage_dir = DYNAMIC_CONFIG.get("storage_dir")

if not storage_dir:
    raise RuntimeError("Configuration missing 'storage_dir'")

# --- Scheduler Setup ---
scheduler = AsyncIOScheduler()

async def enforce_ttl_policy():
    """
    Garbage collection job. Scans the storage directory and removes files
    that have exceeded the dynamically configured Time-To-Live (TTL).
    """
    log = logger.bind(event="ttl_garbage_collection")
    log.info("starting_cleanup_scan")

    current_time = time.time()
    deleted_count = 0

    ttl_seconds = int(DYNAMIC_CONFIG.get("ttl_seconds", 604800)) # Default to 7 days

    if not storage_dir or not os.path.exists(storage_dir):
        log.warning("storage_directory_missing_or_unconfigured")
        return

    try:
        for filename in os.listdir(storage_dir):
            file_path = os.path.join(storage_dir, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getctime(file_path)
                if file_age > ttl_seconds:
                    os.remove(file_path)
                    deleted_count += 1

        log.info("cleanup_finished", payload={"deleted_files": deleted_count, "ttl_applied": ttl_seconds})
    except Exception as e:
        log.error("cleanup_failed", payload={"error": str(e)})


# ==========================================
# DIAGNOSTIC API & APP LIFECYCLE
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensures storage exists, and starts the scheduler."""

    # 1. Ensure the dynamically configured storage directory exists
    os.makedirs(storage_dir, exist_ok=True)
    logger.info("storage_directory_verified", payload={"path": storage_dir})

    # 2. Start the background garbage collection scheduler
    # We run the TTL cleanup check every hour
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
    file_path = os.path.join(storage_dir, safe_filename)

    try:
        # Save the file asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await out_file.write(content)

        # Generate the URI that other components will use
        # Fallback to localhost if a specific base URL isn't in the config
        base_url = DYNAMIC_CONFIG.get("store_base_url", "http://localhost:8001")
        uri = f"{base_url}/files/{safe_filename}"

        log.info("file_uploaded", payload={"filename": file.filename, "size_bytes": os.path.getsize(file_path)})
        return {"uri": uri, "filename": safe_filename}

    except Exception as e:
        log.error("upload_failed", payload={"error": str(e)})
        raise HTTPException(status_code=500, detail="Could not save file")

@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serves a previously uploaded file."""
    file_path = os.path.join(storage_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    files_count = len(os.listdir(storage_dir)) if storage_dir and os.path.exists(storage_dir) else 0

    return {
        "status": "healthy",
        "component": "store",
        "scheduler_running": scheduler.running,
        "files_stored": files_count,
        "active_config": DYNAMIC_CONFIG
    }
