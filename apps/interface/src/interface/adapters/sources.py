import uuid
import httpx
from typing import Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.events import PerceptionGathered
from shared.protocols import ComponentHost
from shared.config import setup_logger

from ..domain.ports import ScrapingClient
from ..infrastructure.clients import HttpxClient, SeleniumClient

logger = setup_logger("scraping_source")

class ScrapingEventSource:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.scheduler = AsyncIOScheduler()
        self.clients: dict[str, ScrapingClient] = {}
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.interval = int(params.get("interval_minutes", 15))
        self.store_api_url = params.get("store_api_url", "http://localhost:8001/files")
        self.targets = params.get("targets", [])

        if self.scheduler.running and self.enabled:
            self.scheduler.reschedule_job('scrape_job', trigger='interval', minutes=self.interval)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component

    async def start(self) -> None:
        if not self._host: raise RuntimeError("ScrapingEventSource not registered")
        self.scheduler.add_job(self._scrape_all, 'interval', minutes=self.interval, id='scrape_job')
        self.scheduler.start()

    async def stop(self) -> None:
        self.scheduler.shutdown()
        for client in self.clients.values():
            await client.close()

    def _get_client(self, backend: str) -> ScrapingClient:
        if backend not in self.clients:
            if backend == "selenium":
                self.clients[backend] = SeleniumClient()
            else:
                self.clients[backend] = HttpxClient()
        return self.clients[backend]

    async def _scrape_all(self):
        if not self.enabled: return
        for target in self.targets:
            await self._scrape_target(target)

    async def _scrape_target(self, target: dict[str, str]):
        url = target["url"]
        backend = target.get("backend", "httpx")
        correlation_id = str(uuid.uuid4())
        log = logger.bind(correlation_id=correlation_id, url=url, backend=backend)

        try:
            # 1. Scrape using the dynamically selected client
            client = self._get_client(backend)
            html_content = await client.fetch_html(url)

            # 2. Upload to the actual Store component!
            async with httpx.AsyncClient() as http_client:
                files = {'file': ('scraped.html', html_content.encode('utf-8'), 'text/html')}
                data = {'retention_policy': 'standard'}
                resp = await http_client.post(self.store_api_url, files=files, data=data)
                resp.raise_for_status()
                uri = resp.json()["uri"]

            # 3. Publish Event
            event = PerceptionGathered(correlation_id=correlation_id, source_url=url, uri=uri)
            await self._host.publish(event, queue="perceptions")
            log.info("perception_published", payload={"uri": uri})

        except Exception as e:
            log.error("scraping_failed", payload={"error": str(e)})

class RSSEventSource:
    """Periodically fetches XML/RSS feeds and uploads them to the Store."""
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.scheduler = AsyncIOScheduler()
        self.client = HttpxClient() # RSS doesn't need Selenium
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.interval = int(params.get("interval_minutes", 60))
        self.store_api_url = params.get("store_api_url", "http://localhost:8001/files")
        self.targets = params.get("targets", [])

        if self.scheduler.running and self.enabled:
            self.scheduler.reschedule_job('rss_job', trigger='interval', minutes=self.interval)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component

    async def start(self) -> None:
        if not self._host: raise RuntimeError("RssEventSource not registered")
        self.scheduler.add_job(self._fetch_all, 'interval', minutes=self.interval, id='rss_job')
        self.scheduler.start()

    async def stop(self) -> None:
        self.scheduler.shutdown()
        await self.client.close()

    async def _fetch_all(self):
        if not self.enabled: return
        for url in self.targets:
            await self._fetch_feed(url)

    async def _fetch_feed(self, url: str):
        correlation_id = str(uuid.uuid4())
        log = logger.bind(correlation_id=correlation_id, url=url, source_type="rss")

        try:
            # 1. Fetch the XML payload
            xml_content = await self.client.fetch_html(url)

            # 2. Upload to Store with the correct mime type
            async with httpx.AsyncClient() as http_client:
                files = {'file': ('feed.xml', xml_content.encode('utf-8'), 'application/rss+xml')}
                data = {'retention_policy': 'standard'}
                resp = await http_client.post(self.store_api_url, files=files, data=data)
                resp.raise_for_status()
                uri = resp.json()["uri"]

            # 3. Publish Event
            event = PerceptionGathered(correlation_id=correlation_id, source_url=url, uri=uri)
            await self._host.publish(event, queue="perceptions")
            log.info("rss_perception_published", payload={"uri": uri})

        except Exception as e:
            log.error("rss_fetch_failed", payload={"error": str(e)})
