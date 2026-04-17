# ana/adapters/registry.py
from typing import Any, Callable, Awaitable

# A strict contract for our gateway actions: takes a dict, returns (payload_bytes, mime_type)
ActionCallable = Callable[[dict[str, Any]], Awaitable[tuple[bytes, str]]]


class GatewayRegistry:
    """Registry to map action keys to concrete async callable actions."""

    def __init__(self) -> None:
        self._table: dict[str, ActionCallable] = {}

    @property
    def table(self) -> dict[str, ActionCallable]:
        return self._table

    def register(self, key: str, gateway_action: ActionCallable) -> None:
        """Registers a new action callable under the given key."""
        self.table[key] = gateway_action
