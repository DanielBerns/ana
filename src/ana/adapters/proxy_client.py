import httpx
import json
from typing import Any, AsyncIterator
import structlog

from ana.agents.inbound_node import ExpectedDomainException

# Instantiate the module-level logger
logger = structlog.get_logger("ana.adapters.proxy_client")

class ProxyClient:
    """
    Adapter for Ana Proxy. Manages authentication state and exposes
    actions compatible with GatewayRegistry's ActionCallable signature.
    """
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token: str | None = None
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    def _get_trace_headers(self) -> dict[str, str]:
        """Extracts the current context correlation ID to propagate to the Proxy."""
        context = structlog.contextvars.get_contextvars()
        correlation_id = context.get("correlation_id")
        return {"X-Correlation-ID": str(correlation_id)} if correlation_id else {}

    async def _ensure_auth(self) -> None:
        """Deterministically authenticates and caches the token."""
        if self.token:
            return

        logger.debug("Requesting new authentication token from Proxy")
        try:
            # Propagate trace ID even on auth requests
            headers = self._get_trace_headers()
            response = await self.client.post(
                "/api/v1/auth/login",
                json={"username": self.username, "password": self.password},
                headers=headers
            )
            response.raise_for_status()
            self.token = response.json().get("access_token")
            logger.info("Successfully authenticated with Proxy")

        except httpx.HTTPStatusError as e:
            logger.error("Authentication failed", status_code=e.response.status_code)
            raise ExpectedDomainException(f"Failed to authenticate with Ana Proxy: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("Network error during authentication", error=str(e))
            raise ExpectedDomainException(f"Network error during authentication: {str(e)}")

    async def fetch_pending_tasks_action(self, parameters: dict[str, Any]) -> tuple[bytes, str]:
        """
        Registry Action: Polls for pending tasks.
        Returns the raw JSON bytes and mime type.
        """
        await self._ensure_auth()

        headers = {"Authorization": f"Bearer {self.token}"}
        headers.update(self._get_trace_headers()) # Inject trace context

        logger.info("Fetching pending tasks from Proxy")
        try:
            response = await self.client.get("/api/v1/tasks/pending", headers=headers)
            response.raise_for_status()

            logger.debug("Tasks fetched successfully", bytes_received=len(response.content))
            return response.content, response.headers.get("Content-Type", "application/json")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Token expired or unauthorized. Clearing cached token.")
                self.token = None
            else:
                logger.error("Failed to fetch tasks", status_code=e.response.status_code)
            raise ExpectedDomainException(f"Failed to fetch tasks: {e.response.status_code}")

    async def upload_report_stream_action(self, parameters: dict[str, Any]) -> tuple[bytes, str]:
        """
        Registry Action: Streams a large report file UP to the proxy.
        Receives an AsyncIterator via parameters to protect proxy memory.
        Returns the proxy's small JSON confirmation.
        """
        await self._ensure_auth()

        file_stream: AsyncIterator[bytes] = parameters.get("file_stream")
        metadata: dict[str, Any] = parameters.get("metadata", {})

        if not file_stream:
            logger.error("Missing 'file_stream' in parameters.")
            raise ExpectedDomainException("Missing 'file_stream' in parameters.")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Report-Metadata": json.dumps(metadata)
        }
        headers.update(self._get_trace_headers()) # Inject trace context

        logger.info("Initiating report upload stream", metadata=metadata)
        try:
            response = await self.client.post(
                "/api/v1/reports",
                content=file_stream,
                headers=headers
            )
            response.raise_for_status()

            logger.info("Report streamed successfully", proxy_response_status=response.status_code)
            return response.content, response.headers.get("Content-Type", "application/json")

        except httpx.HTTPStatusError as e:
            logger.error("Report upload failed", status_code=e.response.status_code)
            raise ExpectedDomainException(f"Report upload failed: {e.response.status_code}")
