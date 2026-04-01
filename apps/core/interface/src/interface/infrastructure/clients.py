import httpx
from typing import Dict, Any

class EdgeClient:
    """Synchronous/Asynchronous HTTP client to communicate with the isolated Edge APIs."""

    def __init__(self, scraper_url: str, store_url: str):
        self.scraper_url = scraper_url
        self.store_url = store_url

    async def scrape(self, url: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.scraper_url}/api/v1/scrape", json={"url": url})
            response.raise_for_status()
            return response.json()

    async def store_blob(self, content: str, filename: str = "payload.txt") -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            files = {'file': (filename, content.encode('utf-8'), 'text/plain')}
            response = await client.post(f"{self.store_url}/api/v1/blobs", files=files)
            response.raise_for_status()
            return response.json()
