from contextlib import asynccontextmanager
from fastapi import FastAPI
from faststream.rabbit.fastapi import RabbitRouter

# Import our strictly typed domain contracts and shared utilities
from shared.events import (
    BaseEvent,
    PerceptionGathered,
    UserPromptReceived,
    ContextRequested,
    ContextProvided,
    CommandIssued
)
from shared.config import setup_logger, fetch_dynamic_config
from shared.protocols import EventHandler, ComponentHost

# Import the domain logic (The Rule Engine)
from controller.domain.rules import RuleEngine, HumanInteractionRule, MaxRetriesRule

# --- Logging Setup ---
logger = setup_logger("controller_component")

# ==========================================
# DYNAMIC CONFIGURATION STATE
# ==========================================
DYNAMIC_CONFIG = fetch_dynamic_config("controller", logger)
rabbitmq_url = DYNAMIC_CONFIG["rabbitmq_url"]

# Initialize the FastStream router
router = RabbitRouter(rabbitmq_url)

# ==========================================
# 1. THE COMPONENT HOST
# ==========================================
class ControllerHost:
    """
    Concrete implementation of ComponentHost for the Controller.
    """
    def __init__(self, faststream_router: RabbitRouter):
        self.router = faststream_router

    async def publish(self, event: BaseEvent, queue: str) -> None:
        await self.router.broker.publish(event, queue=queue)

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        self.router.subscriber(topic)(handler.handle)

host = ControllerHost(router)


# ==========================================
# 2. EVENT HANDLERS (Adapters)
# ==========================================
class PerceptionHandler:
    """Listens for autonomous scraping events and requests context."""
    def __init__(self):
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("perceptions", self)

    async def handle(self, event: PerceptionGathered) -> None:
        log = logger.bind(correlation_id=event.correlation_id)
        log.info("perception_consumed", payload={"uri": event.uri})

        request_event = ContextRequested(
            correlation_id=event.correlation_id,
            query_reference=event.source_url,
            reply_to_topic="context_responses"
        )
        await self._host.publish(request_event, queue="context_requests")
        log.info("context_requested")


class UserPromptHandler:
    """Listens for chat messages and requests user history context."""
    def __init__(self):
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("user_prompts", self)

    async def handle(self, event: UserPromptReceived) -> None:
        log = logger.bind(correlation_id=event.correlation_id)
        log.info("user_prompt_consumed", payload={"user_id": event.user_id})

        request_event = ContextRequested(
            correlation_id=event.correlation_id,
            user_id=event.user_id,
            reply_to_topic="context_responses"
        )
        await self._host.publish(request_event, queue="context_requests")
        log.info("chat_history_requested")


class ContextProvidedHandler:
    """
    The core orchestrator: Takes the retrieved memory, passes it to the pure
    domain Rule Engine, and dispatches the resulting Command to the Actor.
    """
    def __init__(self, engine: RuleEngine):
        self.rule_engine = engine
        self._host: ComponentHost | None = None

    async def register(self, host_component: ComponentHost) -> None:
        self._host = host_component
        await host_component.subscribe("context_responses", self)

    async def handle(self, event: ContextProvided) -> None:
        log = logger.bind(correlation_id=event.correlation_id)
        log.info("context_received", payload={"history_items": len(event.history)})

        # 1. PURE DOMAIN LOGIC: Delegate decision making to the Rule Engine
        decision = self.rule_engine.process(event, event.history)

        # 2. DISPATCH: Wrap the domain's decision in an event and send it
        command = CommandIssued(
            correlation_id=event.correlation_id,
            instruction=decision.instruction,
            user_id=event.user_id,
            context_data=decision.context_payload
        )

        await self._host.publish(command, queue="commands")
        log.info("command_issued", payload={"instruction": decision.instruction})


# ==========================================
# 3. INSTANTIATION & APP LIFECYCLE
# ==========================================

# Instantiate the domain logic (Rule Engine)
max_retries = DYNAMIC_CONFIG.get("max_retries", 3)
rule_engine = RuleEngine(
    rules=[
        HumanInteractionRule(),
        MaxRetriesRule(max_failures=max_retries)
    ],
    default_instruction="process_data"
)

# Instantiate the handlers
perception_handler = PerceptionHandler()
user_prompt_handler = UserPromptHandler()
context_provided_handler = ContextProvidedHandler(engine=rule_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Register our domains/adapters to the Host
    await perception_handler.register(host)
    await user_prompt_handler.register(host)
    await context_provided_handler.register(host)

    # 2. Start the messaging lifecycle
    async with router.lifespan_context(app):
        logger.info("controller_startup_complete")
        yield

# Initialize the FastAPI app and attach the FastStream router
app = FastAPI(lifespan=lifespan, title="Ana Controller Component")
app.include_router(router)

@app.get("/diagnostic")
async def diagnostic_endpoint():
    """Lightweight read-only API for the Inspector."""
    return {
        "status": "healthy",
        "component": "controller",
        "active_config": DYNAMIC_CONFIG,
        "active_rules": [type(r).__name__ for r in rule_engine.rules]
    }
