from typing import Protocol, TypeVar, Dict, Type

from shared.infrastructure import RabbitMQAdapter
from shared.events import ActionRequired, CommandIssued
from controller.domain.decisions import DomainDecision, ActionDecision, CommandDecision

TDecision = TypeVar("TDecision", bound=DomainDecision, contravariant=True)

class PublisherStrategy(Protocol[TDecision]):
    """Port defining how a domain decision gets published to infrastructure."""
    async def publish(self, decision: TDecision, adapter: RabbitMQAdapter, correlation_id: str) -> None:
        ...

class ActionPublisherStrategy:
    """Adapter translating ActionDecision to ActionRequired event."""
    async def publish(self, decision: ActionDecision, adapter: RabbitMQAdapter, correlation_id: str) -> None:
        action = ActionRequired(
            correlation_id=correlation_id,
            action_type=decision.action_type,
            payload=decision.payload
        )
        await adapter.publish(action, routing_key="actions")

class CommandPublisherStrategy:
    """Adapter translating CommandDecision to CommandIssued event."""
    async def publish(self, decision: CommandDecision, adapter: RabbitMQAdapter, correlation_id: str) -> None:
        cmd = CommandIssued(
            correlation_id=correlation_id,
            instruction=decision.instruction,
            context_data=decision.context_data
        )
        await adapter.publish(cmd, routing_key="commands")



class DecisionPublisherRegistry:
    def __init__(self):
        # Maps the strict Domain model type to its corresponding infrastructure Strategy
        self._strategies: Dict[Type[DomainDecision], PublisherStrategy] = {}

    def register(self, decision_type: Type[DomainDecision], strategy: PublisherStrategy) -> None:
        self._strategies[decision_type] = strategy

    async def publish(self, decision: DomainDecision, adapter: RabbitMQAdapter, correlation_id: str) -> None:
        strategy = self._strategies.get(type(decision))
        if not strategy:
            raise NotImplementedError(f"No publishing strategy registered for domain model: {type(decision).__name__}")

        await strategy.publish(decision, adapter, correlation_id)
