# ana/application.py


from faststream import FastStream, ContextRepo
from faststream.rabbit import RabbitBroker

from ana.adapters.faststream_bus import FastStreamMessageBus
from ana.adapters.local_storage import LocalResourceRepository

# Import all agent routers
from ana.agents.inbound_node import inbound_router
from ana.agents.domain_agents import domain_router
from ana.agents.reporter_node import reporter_router

broker = RabbitBroker("amqp://localhost:5672/")

# Create the concrete adapter instances
message_bus = FastStreamMessageBus(broker)
local_repository = LocalResourceRepository()

# Initialize without the broken context dictionary
app = FastStream(broker)

@app.on_startup
async def setup_context(context: ContextRepo):
    context.set_global("bus", message_bus)
    context.set_global("repository", local_repository)
    # Note: In a live system, you would also initialize and inject the Gel (EdgeDB)
    # KnowledgeGraph adapter here.

# Register all routes (The entire CQRS pipeline)
app.broker.include_router(inbound_router)
app.broker.include_router(domain_router)
app.broker.include_router(reporter_router)
