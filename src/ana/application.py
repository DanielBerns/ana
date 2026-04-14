# ana/application.py

from faststream import FastStream, ContextRepo
from faststream.rabbit import RabbitBroker

from ana.adapters.faststream_bus import FastStreamMessageBus
from ana.adapters.local_storage import LocalResourceRepository

# Import all agent routers
from ana.agents.inbound_node import inbound_router
from ana.agents.domain_agents import domain_router
from ana.agents.reporter_node import reporter_router
from ana.adapters.registry import GatewayRegistry
from ana.adapters.http_actions import fetch_json_api, post_to_proxy

broker = RabbitBroker("amqp://localhost:5672/")

# Create the concrete adapter instances
message_bus = FastStreamMessageBus(broker)
local_repository = LocalResourceRepository()
# Initialize and populate the registry

proxy_client = ProxyAPIClient(base_url="...", username="...", password="...")

# These perfectly match ActionCallable [[dict[str, Any]], Awaitable[tuple[bytes, str]]]

gateway_registry = GatewayRegistry()
gateway_registry.register("proxy_fetch_tasks", proxy_client.fetch_pending_tasks_action)
gateway_registry.register("proxy_upload_report", proxy_client.upload_report_stream_action)
gateway_registry.register("http_get_json", fetch_json_api)
gateway_registry.register("http_post_proxy", post_to_proxy)

# Initialize without the broken context dictionary
app = FastStream(broker)

@app.on_startup
async def setup_context(context: ContextRepo):
    # Inject core dependencies
    context.set_global("bus", message_bus)
    context.set_global("repository", local_repository)
    # Inject the configured action registry
    context.set_global("registry", action_registry)
