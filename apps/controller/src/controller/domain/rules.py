# apps/controller/src/controller/domain/rules.py
import uuid
from typing import Any
from shared.events import BaseEvent, CommandIssued
from shared.protocols import ComponentHost
from shared.config import setup_logger

logger = setup_logger("controller_rules")

class BaseRule:
    """The base contract for all active rules."""
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.enabled = True
        self.update_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        """Standard configuration update. Subclasses can override to add specific fields."""
        self.enabled = config.get("enabled", True)

    async def register(self, host: ComponentHost) -> None:
        """Binds the rule to the message broker so it can send/receive events."""
        self._host = host
        await self.setup_subscriptions()

    async def setup_subscriptions(self) -> None:
        """Optional: Subclasses can override this to listen to specific queues."""
        pass

    async def evaluate(self, context_data: Any) -> None:
        """The core logic of the rule. Must be implemented by subclasses."""
        raise NotImplementedError


class ETLRoutingRule(BaseRule):
    """Routes specific scraped data to the Actor for ETL processing."""

    def update_config(self, config: dict[str, Any]) -> None:
        super().update_config(config)
        # Load the target URLs from the YAML config
        self.target_domains = config.get("target_domains", [])

    async def evaluate(self, context_event: Any) -> None:
        if not self.enabled or not self._host:
            return

        # We assume context_event is a ContextProvided event containing our trigger
        trigger = getattr(context_event, "trigger_event", None)

        # If the trigger was a perception gathered from the Interface
        if trigger and trigger.get("event_type") == "PerceptionGathered":
            source_url = trigger.get("source_url", "")

            # Check if the URL matches our configurable target domains
            if any(domain in source_url for domain in self.target_domains):
                correlation_id = str(uuid.uuid4())
                uri = trigger.get("uri")

                # The Rule actively publishes the command to the broker itself!
                command = CommandIssued(
                    correlation_id=correlation_id,
                    target_component="actor",
                    instruction="extract_timeseries_data",
                    payload={"source_uri": uri, "origin_url": source_url}
                )
                await self._host.publish(command, queue="commands")

                logger.info(
                    "etl_rule_triggered",
                    payload={"domain": source_url, "instruction": command.instruction}
                )


class RuleEngine:
    def __init__(self, config: dict[str, Any]):
        self._host: ComponentHost | None = None
        self.rules: dict[str, BaseRule] = {}
        self.update_config(config)

    def update_config(self, config: dict[str, Any]) -> None:
        # Here you map config names to actual Python classes
        rule_classes = {
            "ETLRoutingRule": ETLRoutingRule,
            # Add other rules here as you build them
        }

        for rule_name, rule_class in rule_classes.items():
            rule_config = config.get(rule_name, {})
            if rule_name not in self.rules:
                self.rules[rule_name] = rule_class(rule_config)
            else:
                self.rules[rule_name].update_config(rule_config)

    async def register(self, host: ComponentHost) -> None:
        self._host = host
        for rule in self.rules.values():
            await rule.register(host)

    async def evaluate_all(self, context_data: Any) -> None:
        for rule in self.rules.values():
            if rule.enabled:
                await rule.evaluate(context_data)
