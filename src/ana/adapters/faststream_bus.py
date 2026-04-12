# ana/adapters/faststream_bus.py
from faststream.rabbit import RabbitBroker, RabbitExchange, ExchangeType

from ana.domain.messages import BaseCommand, BaseEvent
from ana.ports.interfaces import MessageBusPort

# --- Exchange Definitions ---
# Enforcing Command/Event Segregation
commands_exchange = RabbitExchange("ana.commands", type=ExchangeType.TOPIC)
events_exchange = RabbitExchange("ana.events", type=ExchangeType.TOPIC)

# Dead Letter Exchange for the Fail Fast / explicit NACK mechanism
dlx_exchange = RabbitExchange("ana.dlx", type=ExchangeType.TOPIC)


class FastStreamMessageBus(MessageBusPort):
    """Adapter to publish domain messages to RabbitMQ via FastStream."""

    def __init__(self, broker: RabbitBroker):
        self.broker = broker

    async def publish_command(self, routing_key: str, command: BaseCommand) -> None:
        """Publishes a command to the commands topic exchange."""
        await self.broker.publish(
            message=command,
            exchange=commands_exchange,
            routing_key=routing_key
        )

    async def publish_event(self, routing_key: str, event: BaseEvent) -> None:
        """Publishes an immutable historical fact to the events topic exchange."""
        await self.broker.publish(
            message=event,
            exchange=events_exchange,
            routing_key=routing_key
        )
