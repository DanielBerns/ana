# controller/domain/rules.py
from typing import List, Dict, Any

class SymbolicRuleEngine:
    """
    A deterministic inference engine.
    It maps statistical facts (intents) to symbolic system actions.
    """

    def process_task_event(self, task_name: str, status: str, result_summary: str) -> List[Dict[str, Any]]:
        """
        Parses the raw task results and routes them to specific symbolic evaluations.
        Raises ValueError if the string format is invalid, which the adapter will catch safely.
        """
        if status != "success":
            return [] # In a full system, you might dispatch an error-handling action here

        if task_name == "evaluate_user_intent":
            parts = result_summary.split("|")
            if len(parts) != 2:
                raise ValueError(f"Invalid intent format: {result_summary}")

            intent = parts[0]
            try:
                confidence = float(parts[1])
            except ValueError:
                raise ValueError(f"Confidence must be numeric, got: {parts[1]}")

            return self.evaluate_intent(intent, confidence)

        elif task_name == "extract_facts":
            parts = result_summary.split("|")
            if len(parts) != 2:
                raise ValueError(f"Invalid extract_facts format: {result_summary}")
            try:
                keywords = parts[0][len('keywords:'):]
                uri = parts[1][len('uri:'):]
            except IndexError:
                raise ValueError(f"Malformed key-value pairs: {result_summary}")

            return [{
                "type": "action",
                "action_type": "reply_to_chat",
                "payload": f"Analysis complete for {uri}. Key symbolic entities extracted: [{keywords}]"
            }]

        return []

    def evaluate_intent(self, intent: str, confidence: float) -> List[Dict[str, Any]]:
        """
        Evaluates a perceived intent and returns a list of required actions.
        """
        if confidence < 0.50:
            return [{
                "type": "action",
                "action_type": "reply_to_chat",
                "payload": f"I am only {confidence*100:.1f}% confident in my perception. Could you be more precise?"
            }]

        if intent == "intent_diagnostic":
            return [{
                "type": "action",
                "action_type": "reply_to_chat",
                "payload": "Diagnostic verified. Neurosymbolic perception and symbolic reasoning layers are strictly deterministic and online."
            }]

        elif intent == "intent_greeting":
            return [{
                "type": "action",
                "action_type": "reply_to_chat",
                "payload": "Greetings, Operator. Ana is awaiting your instruction."
            }]

        elif intent == "intent_scrape":
            return [
                {
                    "type": "action",
                    "action_type": "reply_to_chat",
                    "payload": "Acknowledged. I will dispatch a configuration to the Edge ETL Harvester immediately."
                },
                {
                    "type": "command",
                    "instruction": "execute_etl_pipeline",
                    "context_data": {
                        "pipeline_config": {
                            "source": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/403",
                            "extractor": "HttpExtractor",
                            "transformer": "DOMTransformer",
                            "loader": "YamlLoader",
                            "transformer_kwargs": {"target_selector": "p"}
                        }
                    }
                }
            ]
        else:
            return [{
                "type": "action",
                "action_type": "reply_to_chat",
                "payload": f"Symbolic mapping failure. Concept '{intent}' is recognized but has no assigned operational rule."
            }]

