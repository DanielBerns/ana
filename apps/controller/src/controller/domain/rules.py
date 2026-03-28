from typing import Protocol, Any, Optional
from pydantic import BaseModel

# Import the BaseEvent from our shared contracts
from shared.events import BaseEvent

class RuleResult(BaseModel):
    """The concrete decision outputted by the Rule Engine."""
    instruction: str
    context_payload: dict[str, Any]


class Rule(Protocol):
    """
    The structural contract for a single evaluation criteria.
    """
    def evaluate(self, event: BaseEvent, history: list[dict[str, Any]]) -> Optional[RuleResult]:
        """
        Evaluates the event and history.
        Returns a RuleResult if the rule triggers, otherwise returns None to pass control to the next rule.
        """
        ...


# ==========================================
# CONCRETE RULE IMPLEMENTATIONS
# ==========================================

class HumanInteractionRule:
    """
    Rule 1: If the event originated from a specific human user,
    prioritize generating a chat reply.
    """
    def evaluate(self, event: BaseEvent, history: list[dict[str, Any]]) -> Optional[RuleResult]:
        # Since we use duck typing, we check if the event has a user_id attribute
        user_id = getattr(event, "user_id", None)

        if user_id is not None:
            return RuleResult(
                instruction="generate_chat_reply",
                context_payload={"reason": "human_interaction_detected", "user_id": user_id}
            )
        return None


class MaxRetriesRule:
    """
    Rule 2: If the system has failed the same task multiple times recently,
    stop processing and escalate.
    """
    def __init__(self, max_failures: int = 3):
        self.max_failures = max_failures

    def evaluate(self, event: BaseEvent, history: list[dict[str, Any]]) -> Optional[RuleResult]:
        # Count recent failures in the provided history context
        failure_count = sum(1 for record in history if record.get("status") == "failure")

        if failure_count >= self.max_failures:
            return RuleResult(
                instruction="escalate_to_human",
                context_payload={
                    "reason": "max_retries_exceeded",
                    "failures": failure_count
                }
            )
        return None


# ==========================================
# THE RULE ENGINE
# ==========================================

class RuleEngine:
    """
    Iterates through a prioritized list of Rules.
    Returns the decision of the first matching Rule, or a default fallback.
    """
    def __init__(self, rules: list[Rule], default_instruction: str = "process_data"):
        self.rules = rules
        self.default_instruction = default_instruction

    def process(self, event: BaseEvent, history: list[dict[str, Any]]) -> RuleResult:
        """
        Pure business logic execution. No async code, no I/O.
        """
        for rule in self.rules:
            result = rule.evaluate(event, history)
            if result:
                return result

        # Fallback if no specific rules are triggered
        return RuleResult(
            instruction=self.default_instruction,
            context_payload={"reason": "default_fallback"}
        )
