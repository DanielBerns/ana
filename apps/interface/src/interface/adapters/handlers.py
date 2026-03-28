from typing import Any
from shared.events import ActionRequired
from shared.protocols import ComponentHost
from shared.config import setup_logger

logger = setup_logger("proxy_handler")

class ProxyActionHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)
        self.proxy_url = params.get("proxy_url", "http://localhost:3000/webhook")

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("actions", self)

    async def handle(self, event: ActionRequired) -> None:
        if not self.enabled: return

        log = logger.bind(correlation_id=event.correlation_id)
        if event.action_type == "reply_to_chat" and event.user_id:
            payload = {"user_id": event.user_id, "reply": event.payload}
            log.info("pushed_reply_to_proxy", payload={"proxy_url": self.proxy_url, "data": payload})
