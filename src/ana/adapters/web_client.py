import httpx
from typing import Any
import structlog

from ana.agents.inbound_node import ExpectedDomainException

logger = structlog.get_logger("ana.adapters.web_client")


class PublicWebsiteClient:
    """
    Adapter for public websites. No need to manage authentication state and exposes
    actions compatible with GatewayRegistry's ActionCallable signature.
    """

    def __init__(self, base_url: str = ""):
        # base_url can be empty if full URLs are passed via parameters
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=60.0)

    def _get_trace_headers(self) -> dict[str, str]:
        context = structlog.contextvars.get_contextvars()
        correlation_id = context.get("correlation_id")
        return {"X-Correlation-ID": str(correlation_id)} if correlation_id else {}

    async def http_get_action(self, parameters: dict[str, Any]) -> tuple[bytes, str]:
        """
        Registry Action: get content from a public website (no need for auth credentials)
        Returns raw bytes and mime type. Expects 'url' in parameters.
        """
        target_url = parameters.get("url")
        if not target_url:
            logger.error("Missing 'url' in parameters dictionary")
            raise ExpectedDomainException(
                "Missing 'url' in parameters to fetch public website."
            )

        # Optional: Send our correlation ID. Some CDNs log custom headers, which helps if we need to debug edge issues.
        headers = self._get_trace_headers()

        logger.info("Fetching content from public website", target_url=target_url)

        try:
            response = await self.client.get(target_url, headers=headers)
            response.raise_for_status()

            logger.debug(
                "Successfully fetched public content",
                target_url=target_url,
                bytes_received=len(response.content),
            )
            return response.content, response.headers.get(
                "Content-Type", "application/octet-stream"
            )

        except httpx.HTTPStatusError as e:
            logger.warning(
                "HTTP error fetching public website",
                target_url=target_url,
                status_code=e.response.status_code,
            )
            raise ExpectedDomainException(
                f"Failed to fetch public URL {target_url}: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(
                "Network error connecting to public website",
                target_url=target_url,
                error=str(e),
            )
            raise ExpectedDomainException(f"Network error: {str(e)}")
