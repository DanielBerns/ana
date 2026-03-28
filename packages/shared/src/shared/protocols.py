from typing import Protocol, Any, Optional
from .events import BaseEvent

class EventHandler(Protocol):
    """
    Reacts to events, encapsulates external interactions, and emits new events.
    Must be able to register itself with a ComponentHost.
    """
    async def register(self, host: "ComponentHost") -> None:
        """Registers itself with the host for specific event types."""
        ...

    async def handle(self, event: BaseEvent) -> None:
        """The core logic encapsulated within the handler."""
        ...

class EventSource(Protocol):
    """
    Generates events autonomously and eventually stops.
    Must be registered with a ComponentHost to publish events.
    """
    async def register(self, host: "ComponentHost") -> None:
        """Links the source to the host before running."""
        ...

    async def start(self) -> None:
        """The internal script/clock that emits events and terminates."""
        ...

class ComponentHost(Protocol):
    """
    The interface exposed by the application facades (Controller, Actor, Interface).
    It acts as the bridge between the messaging broker and the domain logic.
    """
    async def publish(self, event: BaseEvent, queue: str) -> None:
        """Allows handlers and sources to emit new events to a specific queue."""
        ...

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Allows handlers to register themselves to listen to specific topics."""
        ...
