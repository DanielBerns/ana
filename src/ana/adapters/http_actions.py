# ana/adapters/http_actions.py
import httpx
from typing import Any
from ana.agents.inbound_node import ExpectedDomainException

async def fetch_json_api(parameters: dict[str, Any]) -> tuple[bytes, str]:
    """Action to fetch data from a REST API."""
    url = parameters.get("url")
    if not url:
        raise ExpectedDomainException("Missing 'url' in action parameters.")

    headers = parameters.get("headers", {})

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)

            # Map standard HTTP errors to our expected domain failures
            if response.status_code in [401, 403, 404, 429, 500, 503]:
                raise ExpectedDomainException(f"External API returned {response.status_code}: {response.reason_phrase}")

            response.raise_for_status()

            mime_type = response.headers.get("Content-Type", "application/json")
            return response.content, mime_type

        except httpx.RequestError as e:
            # Network level failures (DNS, timeouts)
            raise ExpectedDomainException(f"Network request failed: {str(e)}")

async def post_to_proxy(parameters: dict[str, Any]) -> tuple[bytes, str]:
    """Action to post data to a remote server (like your public proxy)."""
    url = parameters.get("url")
    payload = parameters.get("payload", {})
    headers = parameters.get("headers", {})

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise ExpectedDomainException(f"Post failed with status {response.status_code}")

            return response.content, response.headers.get("Content-Type", "application/json")
        except httpx.RequestError as e:
            raise ExpectedDomainException(f"Network request failed: {str(e)}")
