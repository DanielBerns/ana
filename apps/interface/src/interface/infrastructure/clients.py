import asyncio
import httpx
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class HttpxClient:
    """Lightweight, fast client for static HTML scraping."""
    def __init__(self):
        self.client = httpx.AsyncClient()

    async def fetch_html(self, url: str) -> str:
        response = await self.client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text

    async def close(self) -> None:
        await self.client.aclose()


class SeleniumClient:
    """Heavy client for JavaScript-rendered SPA scraping."""
    def __init__(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        # Automatically installs the correct ChromeDriver version
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def _fetch_sync(self, url: str) -> str:
        self.driver.get(url)
        # You could add explicit Selenium waits here if needed
        return self.driver.page_source

    async def fetch_html(self, url: str) -> str:
        # Run synchronous selenium in a background thread
        return await asyncio.to_thread(self._fetch_sync, url)

    async def close(self) -> None:
        await asyncio.to_thread(self.driver.quit)
