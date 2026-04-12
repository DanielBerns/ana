# main.py
from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream.exceptions import RejectMessage

from ana.adapters.faststream_bus import commands_exchange, dlx_exchange

# Initialize the broker (defaults to amqp://guest:guest@localhost:5672/)
broker = RabbitBroker("amqp://localhost:5672/")
app = FastStream(broker)

# Define a standard queue with a configured Dead Letter Exchange
# If a message is NACKed with requeue=False, RabbitMQ routes it here.
inbound_queue = RabbitQueue(
    "ana.queue.inbound_nodes",
    routing_key="command.ionode.inbound.*",
    dlx_exchange=dlx_exchange
)

# --- Subscriptions Blueprint (Phase 4 Preview) ---
# We use Pydantic DTOs directly. FastStream handles deserialization.

# @broker.subscriber(queue=inbound_queue, exchange=commands_exchange)
# async def handle_inbound_command(command: ExecuteIONodeCommand):
#     try:
#         # Boundary execution logic goes here...
#         pass
#     except ExpectedDomainException:
#         # E.g., external API is down -> emit IONodeFailureEvent, acknowledge message normally
#         pass
#     except Exception as e:
#         # UNEXPECTED STATE: Explicit NACK (requeue=False)
#         # FastStream's RejectMessage exception explicitly NACKs the message,
#         # triggering the queue's dlx_exchange routing.
#         # After rejecting, the orchestrator/container can be allowed to crash.
#         raise RejectMessage() from e
