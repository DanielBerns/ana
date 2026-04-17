# ana/ports/interfaces.py
from typing import Any, Protocol

from ana.domain.messages import BaseCommand, BaseEvent
from ana.domain.tuples import Tuple4


class MessageBusPort(Protocol):
    """Outbound port for publishing events and commands to the broker."""

    async def publish_event(self, routing_key: str, event: BaseEvent) -> None: ...

    async def publish_command(self, routing_key: str, command: BaseCommand) -> None: ...


class ResourceRepositoryPort(Protocol):
    """Port for interacting with raw file storage."""

    async def save(self, stream: bytes, metadata: dict[str, Any]) -> str:
        """Saves the byte stream and returns the assigned resource_uri."""
        ...

    async def fetch(self, resource_uri: str) -> bytes:
        """Retrieves the byte stream for a given resource_uri."""
        ...


class KnowledgeGraphPort(Protocol):
    """Port for the Deterministic Domain to interact with the Graph DB."""

    async def merge_tuples(self, tuples: list[Tuple4]) -> None:
        """Idempotently writes 4-tuples. Must not duplicate existing data."""
        ...

    async def query(
        self, query_string: str, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Executes read queries for Reasoner pathfinding and rule engines."""
        ...
