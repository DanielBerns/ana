# ana/adapters/proxy_client.py
import httpx
import json
from typing import Any, AsyncIterator
from ana.agents.inbound_node import ExpectedDomainException

class ProxyAPIClient:
    """
    Adapter for Ana Proxy. Manages authentication state and exposes
    actions compatible with GatewayRegistry's ActionCallable signature.
    """
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token: str | None = None
        # Use a single client session for connection pooling
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    async def _ensure_auth(self) -> None:
        """Deterministically authenticates and caches the token."""
        if self.token:
            return

        try:
            response = await self.client.post(
                "/api/v1/auth/login",
                json={"username": self.username, "password": self.password}
            )
            response.raise_for_status()
            self.token = response.json().get("access_token")
        except httpx.HTTPStatusError as e:
            raise ExpectedDomainException(f"Failed to authenticate with Ana Proxy: {e.response.status_code}")
        except httpx.RequestError as e:
            raise ExpectedDomainException(f"Network error during authentication: {str(e)}")

    async def fetch_pending_tasks_action(self, parameters: dict[str, Any]) -> tuple[bytes, str]:
        """
        Registry Action: Polls for pending tasks.
        Returns the raw JSON bytes and mime type.
        """
        await self._ensure_auth()
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = await self.client.get("/api/v1/tasks/pending", headers=headers)
            response.raise_for_status()
            return response.content, response.headers.get("Content-Type", "application/json")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                self.token = None # Clear token on unauthorized, will retry next tick
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
            raise ExpectedDomainException("Missing 'file_stream' in parameters.")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Report-Metadata": json.dumps(metadata) # Passing metadata via header
        }

        try:
            # httpx automatically uses Transfer-Encoding: chunked when content is an AsyncIterator
            response = await self.client.post(
                "/api/v1/reports",
                content=file_stream,
                headers=headers
            )
            response.raise_for_status()
            return response.content, response.headers.get("Content-Type", "application/json")
        except httpx.HTTPStatusError as e:
            raise ExpectedDomainException(f"Report upload failed: {e.response.status_code}")
