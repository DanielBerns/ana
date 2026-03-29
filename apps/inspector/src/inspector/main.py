import os
from typing import Any
import httpx
from fastapi import FastAPI, Depends, Request, Form
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import asyncio

from shared.config import setup_logger, fetch_dynamic_config

logger = setup_logger("inspector_component")
DYNAMIC_CONFIG = fetch_dynamic_config("inspector", logger)
security = HTTPBasic()

# Setup Templates relative to the current file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI(title="Ana Inspector Component")

# --- Security ---
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    config_user = DYNAMIC_CONFIG.get("admin_username", "admin")
    config_pass = DYNAMIC_CONFIG.get("admin_password", "admin")
    if credentials.username != config_user or credentials.password != config_pass:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Basic"})
    return credentials.username


# --- Dashboard ---
async def fetch_inspector(client: httpx.AsyncClient, name: str, url: str):
    try:
        response = await client.get(url, timeout=2.0)
        return name, response.json()
    except Exception as e:
        logger.error("inspector_fetch_failed", payload={"component": name, "error": str(e)})
        return name, {"status": "offline", "error": str(e)}

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(verify_credentials)):
    targets = DYNAMIC_CONFIG.get("components_to_monitor", {})
    async with httpx.AsyncClient() as client:
        tasks = [fetch_inspector(client, name, url) for name, url in targets.items()]
        results = await asyncio.gather(*tasks)

    inspectors = dict(results)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"request": request, "inspectors": inspectors})

# --- Store Browser (Read/Write) ---
STORE_API_BASE = "http://localhost:8001"

@app.get("/browser/store", response_class=HTMLResponse)
async def store_browser(request: Request, username: str = Depends(verify_credentials)):
    """Renders the main layout for the Store Browser."""
    return templates.TemplateResponse(request=request, name="store.html", context={"request": request})

@app.get("/browser/store/table", response_class=HTMLResponse)
async def store_table(request: Request, username: str = Depends(verify_credentials)):
    """Fetches data from Store component and renders just the table rows for HTMX."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{STORE_API_BASE}/admin/files")
        files = resp.json() if resp.status_code == 200 else []

    return templates.TemplateResponse(request=request, name="store_table.html", context={"request": request, "files": files})

@app.post("/browser/store/{hash_id}/retention", response_class=HTMLResponse)
async def update_retention(request: Request, hash_id: str, policy: str = Form(...), username: str = Depends(verify_credentials)):
    """Proxy action to change retention. Returns nothing, triggering HTMX to refresh the table."""
    async with httpx.AsyncClient() as client:
        await client.patch(f"{STORE_API_BASE}/admin/files/{hash_id}/retention", json={"policy": policy})

    # After updating, we just trigger a table refresh
    headers = {"HX-Trigger": "load"}
    return HTMLResponse(status_code=200, headers=headers)

@app.delete("/browser/store/{hash_id}/delete", response_class=HTMLResponse)
async def delete_file(request: Request, hash_id: str, username: str = Depends(verify_credentials)):
    """Proxy action to delete file. Returns empty string to HTMX, which removes the row from the DOM."""
    async with httpx.AsyncClient() as client:
        await client.delete(f"{STORE_API_BASE}/admin/files/{hash_id}")
    return HTMLResponse(content="")

# --- Database Browser (Read-Only) ---
MEMORY_API_BASE = "http://localhost:8002"

@app.get("/browser/database", response_class=HTMLResponse)
async def database_browser(request: Request, username: str = Depends(verify_credentials)):
    """Renders the main layout for the Database Browser."""
    return templates.TemplateResponse(request=request, name="database.html", context={"request": request})

@app.get("/browser/database/table", response_class=HTMLResponse)
async def database_table(request: Request, table: str = "chat_history", username: str = Depends(verify_credentials)):
    """Fetches data from internal components based on the selected table."""
    rows = []

    if table == "chat_history":
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{MEMORY_API_BASE}/admin/tables/chat_history")
                if resp.status_code == 200:
                    rows = resp.json()
            except Exception as e:
                logger.error("db_fetch_failed", payload={"table": table, "error": str(e)})

    return templates.TemplateResponse(request=request, name="database_table.html", context={"request": request, "rows": rows, "table": table})
