from typing import Protocol, Any, Optional
from .events import BaseEvent

class Configurable(Protocol):
    """Base protocol for dynamically configurable objects."""
    def update_config(self, params: dict[str, Any]) -> None:
        """
        Applies operational config on the fly.
        Must raise ValueError or KeyError if the parameters are invalid.
        """
        ...

class EventHandler(Configurable, Protocol):
    """
    Reacts to events, encapsulates external interactions, and emits new events.
    """
    async def register(self, host: "ComponentHost") -> None:
        """Registers itself with the host for specific event types."""
        ...

    async def handle(self, event: BaseEvent) -> None:
        """The core logic encapsulated within the handler."""
        ...

class EventSource(Configurable, Protocol):
    """
    Generates events autonomously.
    """
    async def register(self, host: "ComponentHost") -> None:
        """Links the source to the host before running."""
        ...

    async def start(self) -> None:
        """Starts the internal script/clock."""
        ...

    async def stop(self) -> None:
        """Gracefully stops the event generation."""
        ...

class ComponentHost(Protocol):
    """The interface exposed by the application facades."""
    async def publish(self, event: BaseEvent, queue: str) -> None:
        ...

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        ...
