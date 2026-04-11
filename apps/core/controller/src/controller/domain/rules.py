# controller/domain/rules.py
from typing import List, Dict, Any, Protocol
from .decisions import DomainDecision, ActionDecision, CommandDecision

# ==========================================
# 1. INTENT STRATEGIES (The inner rules)
# ==========================================
class IntentRule(Protocol):
    """Protocol for a specific intent's operational rule."""
    def evaluate(self) -> List[DomainDecision]:
        ...

class DiagnosticIntentRule:
    def evaluate(self) -> List[DomainDecision]:
        return [ActionDecision(
            action_type="reply_to_chat",
            payload="Diagnostic verified. Neurosymbolic perception and symbolic reasoning layers are strictly deterministic and online."
        )]

class GreetingIntentRule:
    def evaluate(self) -> List[DomainDecision]:
        return [ActionDecision(
            action_type="reply_to_chat",
            payload="Greetings, Operator. Ana is awaiting your instruction."
        )]

class ScrapeIntentRule:
    def evaluate(self) -> List[DomainDecision]:
        return [
            ActionDecision(
                action_type="reply_to_chat",
                payload="Acknowledged. I will dispatch a configuration to the Edge ETL Harvester immediately."
            ),
            CommandDecision(
                instruction="execute_etl_pipeline",
                context_data={
                    "pipeline_config": {
                        "source": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/403",
                        "extractor": "HttpExtractor",
                        "transformer": "DOMTransformer",
                        "loader": "YamlLoader",
                        "transformer_kwargs": {"target_selector": "p"}
                    }
                }
            )
        ]

class IntentRegistry:
    """Manages intent rules and handles global confidence thresholds."""
    def __init__(self):
        self._rules: Dict[str, IntentRule] = {}

    def register(self, intent_name: str, rule: IntentRule) -> None:
        self._rules[intent_name] = rule

    def evaluate(self, intent_name: str, confidence: float) -> List[DomainDecision]:
        # Global domain rule: Low confidence triggers a clarification request
        if confidence < 0.50:
            return [ActionDecision(
                action_type="reply_to_chat",
                payload=f"I am only {confidence*100:.1f}% confident in my perception. Could you be more precise?"
            )]

        rule = self._rules.get(intent_name)
        if not rule:
            return [ActionDecision(
                action_type="reply_to_chat",
                payload=f"Symbolic mapping failure. Concept '{intent_name}' is recognized but has no assigned operational rule."
            )]

        return rule.evaluate()


# ==========================================
# 2. TASK STRATEGIES (The outer handlers)
# ==========================================
class TaskEvaluator(Protocol):
    """Protocol for processing the result of a specific Actor task."""
    def evaluate(self, result_summary: Dict[str, Any]) -> List[DomainDecision]:
        ...

class EvaluateIntentTaskEvaluator:
    def __init__(self, intent_registry: IntentRegistry):
        self.intent_registry = intent_registry

    def evaluate(self, result_summary: Dict[str, Any]) -> List[DomainDecision]:
        intent = result_summary.get("intent", "unknown")
        confidence_str = result_summary.get("confidence", "0.0")

        try:
            confidence = float(confidence_str)
        except ValueError:
            raise ValueError(f"Confidence must be numeric, got: {confidence_str}")

        return self.intent_registry.evaluate(intent, confidence)

class ExtractFactsTaskEvaluator:
    def evaluate(self, result_summary: Dict[str, Any]) -> List[DomainDecision]:
        keywords = result_summary.get("keywords", [])
        uri = result_summary.get("uri", "")

        return [ActionDecision(
            action_type="reply_to_chat",
            payload=f"Analysis complete for {uri}. Key symbolic entities extracted: [{keywords}]"
        )]

class TaskRegistry:
    def __init__(self):
        self._evaluators: Dict[str, TaskEvaluator] = {}

    def register(self, task_name: str, evaluator: TaskEvaluator) -> None:
        self._evaluators[task_name] = evaluator

    def evaluate(self, task_name: str, result_summary: Dict[str, Any]) -> List[DomainDecision]:
        evaluator = self._evaluators.get(task_name)
        if not evaluator:
            return [] # No mapped action for this task
        return evaluator.evaluate(result_summary)


# ==========================================
# 3. THE FACADE
# ==========================================
class SymbolicRuleEngine:
    """
    A deterministic inference engine.
    Acts as a Facade over the Task and Intent evaluation registries.
    """
    def __init__(self):
        # Wire up the inner hexagon components
        self._intent_registry = IntentRegistry()
        self._intent_registry.register("intent_diagnostic", DiagnosticIntentRule())
        self._intent_registry.register("intent_greeting", GreetingIntentRule())
        self._intent_registry.register("intent_scrape", ScrapeIntentRule())

        self._task_registry = TaskRegistry()
        self._task_registry.register("evaluate_user_intent", EvaluateIntentTaskEvaluator(self._intent_registry))
        self._task_registry.register("extract_facts", ExtractFactsTaskEvaluator())

    def process_task_event(self, task_name: str, status: str, result_summary: Dict[str, Any]) -> List[DomainDecision]:
        """
        Parses the raw task results and routes them to specific symbolic evaluations.
        Now strictly returns Pydantic DomainDecision models.
        """
        if status != "success":
            # In a full system, you might dispatch an ErrorHandlingEvaluator here
            return []

        return self._task_registry.evaluate(task_name, result_summary)
