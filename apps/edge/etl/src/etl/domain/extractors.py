from typing import Protocol, Any
import httpx
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import os

class Extractor(Protocol):
    async def extract(self, source: str, **kwargs) -> dict[str, Any]: ...

class HttpExtractor:
    """Fetches static HTML or XML, such as RSS feeds."""
    async def extract(self, source: str, **kwargs) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(source)
            response.raise_for_status()
            return {"content": response.text}

class SeleniumExtractor:
    """
    Bootstraps a headless Firefox browser to render JavaScript.
    Essential for scraping dynamic storefronts to generate price reports.
    """
    async def extract(self, source: str, **kwargs) -> dict[str, Any]:
        options = Options()
        options.add_argument("--headless")
        # In a Docker environment, we connect to a remote geckodriver
        driver_url = os.getenv("SELENIUM_URL", "http://selenium-hub:4444/wd/hub")

        driver = webdriver.Remote(command_executor=driver_url, options=options)
        try:
            driver.get(source)
            # You can easily extend this to accept specific wait conditions via kwargs
            return {"content": driver.page_source}
        finally:
            driver.quit()

class FileSystemExtractor:
    """
    Reads raw text from mounted volumes.
    Perfect for ingesting local data like exported WhatsApp chat files.
    """
    async def parse(self, content: str) -> dict[str, Any]:
        # dummy parser, returns the input as is
        return {"content": content}

    async def extract(self, source: str, **kwargs) -> dict[str, Any]:
        # Source is expected to be a local file path
        if not os.path.exists(source):
            raise FileNotFoundError(f"Local resource not found: {source}")

        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()
            # Added 'await' here because parse() is an async function
            return await self.parse(content)

class ApiExtractor:
    """Handles structured data retrieval using authenticated POST/GET requests."""
    async def extract(self, source: str, **kwargs) -> dict[str, Any]:
        headers = kwargs.get("headers", {})
        payload = kwargs.get("payload", None)
        method = kwargs.get("method", "GET").upper()

        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                response = await client.post(source, headers=headers, json=payload)
            else:
                response = await client.get(source, headers=headers)
            response.raise_for_status()
            return response.json()
