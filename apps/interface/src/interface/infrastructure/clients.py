import asyncio
import httpx
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from shared.config import setup_logger

logger = setup_logger("scraping_clients")

class HttpxClient:
    """Lightweight, fast client for static HTML scraping."""
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_html(self, url: str) -> str:
        logger.info("httpx_fetch_start", payload={"url": url})
        try:
            response = await self.client.get(url, follow_redirects=True)
            response.raise_for_status()
            logger.info("httpx_fetch_success", payload={"url": url, "status": response.status_code, "bytes": len(response.text)})
            return response.text
        except Exception as e:
            logger.error("httpx_fetch_failed", payload={"url": url, "error": str(e)})
            raise

    async def close(self) -> None:
        await self.client.aclose()


class SeleniumClient:
    """Heavy client for JavaScript-rendered SPA scraping."""
    def __init__(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    def _fetch_sync(self, url: str) -> str:
        logger.info("selenium_fetch_start", payload={"url": url})
        try:
            self.driver.get(url)
            html = self.driver.page_source
            logger.info("selenium_fetch_success", payload={"url": url, "bytes": len(html)})
            return html
        except Exception as e:
            logger.error("selenium_fetch_failed", payload={"url": url, "error": str(e)})
            raise

    async def fetch_html(self, url: str) -> str:
        return await asyncio.to_thread(self._fetch_sync, url)

    async def close(self) -> None:
        await asyncio.to_thread(self.driver.quit)
