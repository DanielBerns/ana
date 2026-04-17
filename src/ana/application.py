import uuid
from pathlib import Path

from faststream import FastStream, ContextRepo, BaseMiddleware
from faststream.rabbit import RabbitBroker
import structlog


from ana.adapters.faststream_bus import FastStreamMessageBus
from ana.adapters.local_storage import LocalResourceRepository

# Import all agent routers
from ana.agents.inbound_node import inbound_router
from ana.agents.domain_agents import domain_router
from ana.agents.reporter_node import reporter_router
from ana.adapters.registry import GatewayRegistry
from ana.adapters.proxy_client import ProxyClient
from ana.adapters.web_client import PublicWebsiteClient

# Utils
from ana.utils import read_yaml

from ana.utils import read_yaml

# 1. Define the middleware FIRST
class StructlogMiddleware(BaseMiddleware):
    async def on_receive(self):
        structlog.contextvars.clear_contextvars()
        headers = self.message.headers
        correlation_id = headers.get("correlation_id") or headers.get("X-Correlation-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            message_id=self.message.message_id
        )
        return await super().on_receive()

# 2. Instantiate the broker ONCE, with the middleware attached
broker = RabbitBroker("amqp://localhost:5672/", middlewares=(StructlogMiddleware,))

broker.include_router(inbound_router)
broker.include_router(domain_router)
broker.include_router(reporter_router)

ana_path = Path.home() / "ana"
ana_secrets_path = ana_path / "secrets"
ana_secrets_proxy_file = ana_secrets_path / "ana_proxy" / "credentials.yaml"
ana_secrets_proxy_credentials = read_yaml(ana_secrets_proxy_file)

# Create the concrete adapter instances
message_bus = FastStreamMessageBus(broker)
local_repository = LocalResourceRepository()
gateway_registry = GatewayRegistry()
proxy_client = ProxyClient(
    base_url=ana_secrets_proxy_credentials.get("base_url", "http://127.0.0.1:5000"),
    username=ana_secrets_proxy_credentials.get("username", ""),
    password=ana_secrets_proxy_credentials.get("password", "")
)
# 2. Instantiate the web client
web_client = PublicWebsiteClient()

# 3. FIX: Register the actions mapping EXACTLY to the names in scheduler.yaml
gateway_registry.register("fetch_proxy_info", proxy_client.fetch_pending_tasks_action)
gateway_registry.register("proxy_upload_report", proxy_client.upload_report_stream_action)
gateway_registry.register("scrape_news_ambito", web_client.http_get_action)
gateway_registry.register("scrape_news_infobae", web_client.http_get_action)

app = FastStream(broker)

@app.on_startup
async def setup_context(context: ContextRepo):
    # Inject core dependencies
    context.set_global("bus", message_bus)
    context.set_global("repository", local_repository)
    context.set_global("registry", gateway_registry)
