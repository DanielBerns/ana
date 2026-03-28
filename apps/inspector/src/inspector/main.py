import asyncio
import httpx
import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Import our shared config utilities
from shared.config import setup_logger, fetch_dynamic_config

# --- Logging Setup ---
logger = setup_logger("inspector_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE (Synchronous Boot)
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("inspector", logger)

security = HTTPBasic()

# ==========================================
# AUTHENTICATION
# ==========================================
def verify_admin_user(credentials: HTTPBasicCredentials = Depends(security)):
    """Enforces human user authentication as per the specification."""
    correct_username = secrets.compare_digest(credentials.username, DYNAMIC_CONFIG.get("admin_username", "admin"))
    correct_password = secrets.compare_digest(credentials.password, DYNAMIC_CONFIG.get("admin_password", "admin"))

    if not (correct_username and correct_password):
        logger.warning("failed_login_attempt", payload={"username": credentials.username})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# ==========================================
# inspector AGGREGATION
# ==========================================
async def fetch_inspector(client: httpx.AsyncClient, name: str, url: str):
    """Fetches the inspector state of a single component."""
    try:
        response = await client.get(url, timeout=2.0)
        response.raise_for_status()
        return name, response.json()
    except Exception as e:
        logger.error("inspector_fetch_failed", payload={"component": name, "error": str(e)})
        return name, {"status": "unreachable", "error": str(e)}

# Initialize the FastAPI app
app = FastAPI(title="Ana Inspector Dashboard")

# ==========================================
# DASHBOARD ENDPOINT
# ==========================================
@app.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(username: str = Depends(verify_admin_user)):
    """
    Aggregates system state and renders an HTML report.
    """
    targets = DYNAMIC_CONFIG.get("components_to_monitor", {})

    # Concurrently fetch inspectors from all components
    async with httpx.AsyncClient() as client:
        tasks = [fetch_inspector(client, name, url) for name, url in targets.items()]
        results = await asyncio.gather(*tasks)

    system_state = dict(results)

    # Render a simple, clean HTML dashboard
    html_content = f"""
    <html>
        <head>
            <title>Ana System Inspector</title>
            <style>
                body {{ font-family: sans-serif; background-color: #f4f4f9; color: #333; padding: 20px; }}
                h1 {{ color: #2c3e50; }}
                .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
                .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .status-healthy {{ color: green; font-weight: bold; }}
                .status-unreachable {{ color: red; font-weight: bold; }}
                pre {{ background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; font-size: 0.85em; }}
            </style>
        </head>
        <body>
            <h1>Ana System Inspector Dashboard</h1>
            <p>Welcome, <b>{username}</b>. Here is the real-time aggregated state of the distributed system.</p>
            <div class="grid">
    """

    for name, data in system_state.items():
        status_class = "status-healthy" if data.get("status") == "healthy" else "status-unreachable"
        html_content += f"""
                <div class="card">
                    <h2>{name.capitalize()}</h2>
                    <p>Status: <span class="{status_class}">{data.get('status', 'unknown')}</span></p>
                    <details>
                        <summary>View Raw JSON Data</summary>
                        <pre>{data}</pre>
                    </details>
                </div>
        """

    html_content += """
            </div>
        </body>
    </html>
    """

    return html_content
