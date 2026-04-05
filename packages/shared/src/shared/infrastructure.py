from faststream.rabbit import RabbitBroker, RabbitQueue, RabbitExchange
from faststream.rabbit.fastapi import RabbitRouter
from .events import BaseEvent

RABBITMQ_URL_DEFAULT = "amqp://guest:guest@127.0.0.1:5672/"

class RabbitMQAdapter:
    """
    A unified adapter for RabbitMQ communication.
    Abstracts away FastStream details from the application components.
    """
    def __init__(self, rabbitmq_url: str):
        self.router = RabbitRouter(rabbitmq_url)
        self.broker: RabbitBroker = self.router.broker

    async def publish(self, event: BaseEvent, routing_key: str, exchange_name: str = "ana_events") -> None:
        """Publishes an event to a specific exchange and routing key."""
        exchange = RabbitExchange(exchange_name, auto_delete=False)
        await self.broker.publish(
            event,
            routing_key=routing_key,
            exchange=exchange
        )

    def subscribe(self, queue_name: str, routing_key: str, exchange_name: str = "ana_events"):
        """
        Wires a FastStream consumer directly to an application handler.
        Uses native FastStream routing to avoid FastAPI dependency injection errors.
        """
        exchange = RabbitExchange(exchange_name, auto_delete=False)
        queue = RabbitQueue(name=queue_name, routing_key=routing_key)

        # Return the native FastStream decorator directly
        return self.router.subscriber(queue=queue, exchange=exchange)
