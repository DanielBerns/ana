import os
import uuid
from typing import Any
from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from shared.events import ContextRequested, ContextProvided, ActionRequired, SystemFatalError, ConfigurationUpdated, BaseEvent
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost, Configurable

from .domain.models import Base, MessageRecord

logger = setup_logger("memory_component")

DYNAMIC_CONFIG = fetch_dynamic_config("memory", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]
database_url = DYNAMIC_CONFIG["database_url"]

engine = create_async_engine(database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
router = RabbitRouter(rabbitmq_url)

class MemoryHost:
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router
    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)
    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = MemoryHost(router)

class MemoryHandler:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.history_limit = params.get("history_limit", 10)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("context_requests", self)

    async def handle(self, event: ContextRequested) -> None:
        log = logger.bind(correlation_id=event.correlation_id, user_id=event.user_id)

        async with AsyncSessionLocal() as session:
            # 1. Save the incoming User prompt using the correct attribute
            if event.query_reference and event.user_id:
                new_msg = MessageRecord(user_id=event.user_id, role="user", content=event.query_reference)
                session.add(new_msg)
                await session.commit()

            # 2. Fetch the recent history
            result = await session.execute(
                select(MessageRecord)
                .where(MessageRecord.user_id == event.user_id)
                .order_by(MessageRecord.created_at.desc())
                .limit(self.history_limit)
            )
            records = result.scalars().all()

            # Reverse to chronological order
            history = [{"role": r.role, "content": r.content} for r in reversed(records)]

        # 3. Publish Context
        provided_event = ContextProvided(
            correlation_id=event.correlation_id,
            user_id=event.user_id,
            history=history
        )

        # We dynamically attach trigger_event so the Controller's ChatRoutingRule can see it
        # without breaking Pydantic's strict schema validation!
        provided_event.__dict__["trigger_event"] = {
            "event_type": "ContextRequested",
            "query": event.query_reference
        }

        # Note: Use getattr to safely default the reply_to_topic if it's missing
        await self._host.publish(provided_event, queue=getattr(event, "reply_to_topic", "context_responses"))
        log.info("context_provided", payload={"history_length": len(history)})


class AssistantReplyListener:
    """Listens to actions to save the Assistant's reply into the DB."""
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.update_config(config)

    def update_config(self, params: dict[str, Any]) -> None:
        self.enabled = params.get("enabled", True)

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("actions", self)

    async def handle(self, event: ActionRequired) -> None:
        if not self.enabled or event.action_type != "reply_to_chat" or not event.user_id:
            return

        async with AsyncSessionLocal() as session:
            reply_msg = MessageRecord(user_id=event.user_id, role="assistant", content=str(event.payload))
            session.add(reply_msg)
            await session.commit()
            logger.info("assistant_reply_saved_to_memory", payload={"user_id": event.user_id})

# ... SystemHandler definition remains standard ...
class SystemHandler:
    def __init__(self, component_name: str, registry: dict[str, Configurable]):
        self.component_name = component_name
        self.registry = registry
        self._host: ComponentHost | None = None
    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("system.config_updates", self)
    async def handle(self, event: ConfigurationUpdated) -> None:
        if event.target_component not in (self.component_name, "all"): return
        try:
            for name, config_data in event.new_configuration.get("event_handlers", {}).items():
                if name in self.registry: self.registry[name].update_config(config_data)
        except Exception as e:
            await self._host.publish(SystemFatalError(correlation_id=event.correlation_id, component=self.component_name, error_reason=str(e), bad_configuration=event.new_configuration), queue="system.fatal_errors")
            os._exit(1)


# App Lifecycle
handler_config = DYNAMIC_CONFIG.get("event_handlers", {})
memory_handler = MemoryHandler(handler_config.get("MemoryHandler", {}))
reply_listener = AssistantReplyListener(handler_config.get("AssistantReplyListener", {}))

registry: dict[str, Configurable] = {
    "MemoryHandler": memory_handler,
    "AssistantReplyListener": reply_listener
}
system_handler = SystemHandler("memory", registry)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await memory_handler.register(host)
    await reply_listener.register(host)
    await system_handler.register(host)
    logger.info("memory_startup_complete")
    yield

app = FastAPI(lifespan=lifespan, title="Ana Memory Component")
app.include_router(router)

@app.get("/inspector")
async def inspector_endpoint():
    return {"status": "healthy", "component": "memory", "active_config": DYNAMIC_CONFIG}

# ==========================================
# ADMIN ENDPOINTS (For Inspector BFF)
# ==========================================
@app.get("/admin/tables/chat_history")
async def admin_chat_history(limit: int = 50, offset: int = 0):
    """Exposes the chat_history table for the Inspector UI."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MessageRecord).order_by(MessageRecord.created_at.desc()).offset(offset).limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in records
        ]
