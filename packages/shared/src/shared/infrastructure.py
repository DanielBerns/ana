import functools
from faststream.rabbit import RabbitBroker, RabbitQueue, RabbitExchange
from faststream.rabbit.fastapi import RabbitRouter
from typing import Callable, Any, Awaitable
from .events import BaseEvent
from .logger import correlation_id_var

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
        A decorator to wire a FastStream consumer to an application handler.
        Automatically sets the contextvar for logging correlation.
        """
        exchange = RabbitExchange(exchange_name, auto_delete=False)
        queue = RabbitQueue(name=queue_name, routing_key=routing_key)

        def decorator(handler_func: Callable):
            @functools.wraps(handler_func)
            async def wrapper(*args, **kwargs):
                # FastStream passes the parsed Pydantic model via args or kwargs.
                # We extract it safely to grab the correlation ID.
                event = args[0] if args else list(kwargs.values())[0]

                # 1. Inject the correlation ID into the execution context
                token = correlation_id_var.set(getattr(event, "correlation_id", "unknown"))
                try:
                    # 2. Execute the domain/application handler
                    return await handler_func(*args, **kwargs)
                finally:
                    # 3. Clean up the context
                    correlation_id_var.reset(token)

            # Apply the FastStream subscriber to our perfectly wrapped function
            return self.router.subscriber(queue=queue, exchange=exchange)(wrapper)
        return decorator
