from typing import Protocol, Any
import httpx
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import os
import json

class Extractor(Protocol):
    async def extract(self, source: str, parameters: dict[str, str] | None = None) -> dict[str, Any]: ...

class HttpExtractor:
    """Fetches static HTML or XML, such as RSS feeds."""
    async def extract(self, source: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
        params = parameters or {}
        # Parse the string into a boolean, defaulting to True for security
        verify_ssl = params.get("verify", "true").lower() == "true"

        async with httpx.AsyncClient(timeout=10.0, verify=verify_ssl) as client:
            response = await client.get(source)
            response.raise_for_status()
            return {"content": response.text}

class SeleniumExtractor:
    """Bootstraps a headless Firefox browser to render JavaScript."""
    async def extract(self, source: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
        params = parameters or {}
        options = Options()
        options.add_argument("--headless")

        driver_url = os.getenv("SELENIUM_URL", "http://selenium-hub:4444/wd/hub")
        driver = webdriver.Remote(command_executor=driver_url, options=options)
        try:
            driver.get(source)
            # You can extract wait conditions from `params` here if needed in the future
            return {"content": driver.page_source}
        finally:
            driver.quit()

class FileSystemExtractor:
    """Reads raw text from mounted volumes."""
    async def parse(self, content: str) -> dict[str, Any]:
        return {"content": content}

    async def extract(self, source: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
        params = parameters or {}
        if not os.path.exists(source):
            raise FileNotFoundError(f"Local resource not found: {source}")

        with open(source, 'r', encoding='utf-8') as f:
            content = f.read()
            return await self.parse(content)

class ApiExtractor:
    """Handles structured data retrieval using authenticated POST/GET requests."""
    async def extract(self, source: str, parameters: dict[str, str] | None = None) -> dict[str, Any]:
        params = parameters or {}
        method = params.get("method", "GET").upper()

        # Since parameters is strictly dict[str, str], we decode JSON strings for complex types
        headers_str = params.get("headers")
        headers = json.loads(headers_str) if headers_str else {}

        payload_str = params.get("payload")
        payload = json.loads(payload_str) if payload_str else None

        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "POST":
                response = await client.post(source, headers=headers, json=payload)
            else:
                response = await client.get(source, headers=headers)
            response.raise_for_status()
            return response.json()
