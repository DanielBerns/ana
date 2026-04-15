# ana/application.py

from faststream import FastStream, ContextRepo
from faststream.rabbit import RabbitBroker

from ana.adapters.faststream_bus import FastStreamMessageBus
from ana.adapters.local_storage import LocalResourceRepository
from ana.utils import read_yaml

# Import all agent routers
from ana.agents.inbound_node import inbound_router
from ana.agents.domain_agents import domain_router
from ana.agents.reporter_node import reporter_router
from ana.adapters.registry import GatewayRegistry
from ana.adapters.proxy_client import ProxyClient


broker = RabbitBroker("amqp://localhost:5672/")
ana_path = Path.home / "ana"
ana_secrets_path = ana_path / "secrets"
ana_secrets_proxy_file = ana_secrets_path / "ana_proxy" / "credentials.yaml"
ana_secrets_proxy_credentials = read_yaml(ana_secrets_proxy_file)

# Create the concrete adapter instances
message_bus = FastStreamMessageBus(broker)
local_repository = LocalResourceRepository()
proxy_client = ProxyClient(
    base_url=ana_secrets_proxy_credentials.base_url,
    username=ana_secrets_proxy_credentials.url,
    password=ana_secrets_proxy_credentials.url
)

# Initialize and populate the registry
gateway_registry = GatewayRegistry()
gateway_registry.register("proxy_fetch_tasks", proxy_client.fetch_pending_tasks_action)
gateway_registry.register("proxy_upload_report", proxy_client.upload_report_stream_action)

# Initialize without the broken context dictionary
app = FastStream(broker)

@app.on_startup
async def setup_context(context: ContextRepo):
    # Inject core dependencies
    context.set_global("bus", message_bus)
    context.set_global("repository", local_repository)
    # Inject the configured action registry
    context.set_global("registry", action_registry)
