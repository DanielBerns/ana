# tests/controller/domain/test_rules.py
import pytest
from controller.domain.rules import SymbolicRuleEngine

@pytest.fixture
def engine():
    return SymbolicRuleEngine()

# --- Tests for Intent Evaluation Rules ---

def test_evaluate_intent_low_confidence(engine):
    decisions = engine.evaluate_intent("intent_greeting", 0.49)
    assert len(decisions) == 1
    assert decisions[0]["type"] == "action"
    assert "49.0% confident" in decisions[0]["payload"]

def test_evaluate_intent_diagnostic(engine):
    decisions = engine.evaluate_intent("intent_diagnostic", 0.95)
    assert len(decisions) == 1
    assert decisions[0]["type"] == "action"
    assert "Diagnostic verified" in decisions[0]["payload"]

def test_evaluate_intent_scrape(engine):
    decisions = engine.evaluate_intent("intent_scrape", 0.88)
    assert len(decisions) == 2

    # Check the chat reply
    assert decisions[0]["type"] == "action"
    assert decisions[0]["action_type"] == "reply_to_chat"

    # Check the ETL command dispatch
    assert decisions[1]["type"] == "command"
    assert decisions[1]["instruction"] == "execute_etl_pipeline"
    assert "pipeline_config" in decisions[1]["context_data"]
    assert decisions[1]["context_data"]["pipeline_config"]["extractor"] == "HttpExtractor"

def test_evaluate_intent_unknown(engine):
    decisions = engine.evaluate_intent("intent_make_coffee", 0.99)
    assert len(decisions) == 1
    assert "Symbolic mapping failure" in decisions[0]["payload"]

# --- Tests for the Parsing Anti-Corruption Layer ---

def test_process_task_event_valid_intent(engine):
    decisions = engine.process_task_event("evaluate_user_intent", "success", "intent_greeting|0.85")
    assert len(decisions) == 1
    assert "Greetings, Operator." in decisions[0]["payload"]

def test_process_task_event_valid_facts(engine):
    result_str = "keywords:python,ai,hexagonal|uri:https://example.com"
    decisions = engine.process_task_event("extract_facts", "success", result_str)
    assert len(decisions) == 1
    assert "Analysis complete for https://example.com" in decisions[0]["payload"]
    assert "[python,ai,hexagonal]" in decisions[0]["payload"]

def test_process_task_event_malformed_string_raises_value_error(engine):
    with pytest.raises(ValueError, match="Invalid intent format"):
        engine.process_task_event("evaluate_user_intent", "success", "bad_data_no_separator")

    with pytest.raises(ValueError, match="Confidence must be numeric"):
        engine.process_task_event("evaluate_user_intent", "success", "intent_greeting|not_a_number")

def test_process_task_event_ignored_failure(engine):
    decisions = engine.process_task_event("evaluate_user_intent", "failure", "error details")
    assert len(decisions) == 0
