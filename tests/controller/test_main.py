# tests/controller/test_main.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from shared.events import TaskCompleted, ActionRequired, CommandIssued

# Import the specific handler and the dependencies we need to mock
from controller.main import on_task_completed, adapter, rule_engine, logger

@pytest.fixture
def mock_dependencies(mocker):
    """Fixture to mock out the adapter publisher and the domain engine."""
    # Mock the async publish method
    mocker.patch.object(adapter, 'publish', new_callable=AsyncMock)

    # Mock the synchronous rule engine method
    mocker.patch.object(rule_engine, 'process_task_event', return_value=[])

    # Mock the logger to assert errors
    mocker.patch.object(logger, 'error')
    mocker.patch.object(logger, 'exception')

    return adapter, rule_engine, logger

@pytest.mark.asyncio
async def test_on_task_completed_issues_action(mock_dependencies):
    mock_adapter, mock_engine, _ = mock_dependencies

    # Arrange: Engine will decide an action is required
    mock_engine.process_task_event.return_value = [
        {"type": "action", "action_type": "reply_to_chat", "payload": "Test payload"}
    ]

    event = TaskCompleted(
        task_name="extract_facts",
        status="success",
        result_summary="valid_summary_format"
    )

    # Act
    await on_task_completed(event)

    # Assert: Verify the engine was called with pure data
    mock_engine.process_task_event.assert_called_once_with(
        task_name="extract_facts",
        status="success",
        result_summary="valid_summary_format"
    )

    # Assert: Verify the adapter published the correct Pydantic event
    mock_adapter.publish.assert_called_once()
    published_event = mock_adapter.publish.call_args[0][0]
    assert isinstance(published_event, ActionRequired)
    assert published_event.action_type == "reply_to_chat"
    assert published_event.payload == "Test payload"
    assert published_event.correlation_id == event.correlation_id

@pytest.mark.asyncio
async def test_on_task_completed_issues_command(mock_dependencies):
    mock_adapter, mock_engine, _ = mock_dependencies

    # Arrange: Engine will decide a command is required
    mock_engine.process_task_event.return_value = [
        {"type": "command", "instruction": "update_graph", "context_data": {"node": "A"}}
    ]

    event = TaskCompleted(task_name="evaluate_user_intent", status="success", result_summary="intent|0.99")

    # Act
    await on_task_completed(event)

    # Assert
    mock_adapter.publish.assert_called_once()
    published_event = mock_adapter.publish.call_args[0][0]
    assert isinstance(published_event, CommandIssued)
    assert published_event.instruction == "update_graph"
    assert published_event.context_data == {"node": "A"}

@pytest.mark.asyncio
async def test_on_task_completed_prevents_poison_pill(mock_dependencies):
    mock_adapter, mock_engine, mock_logger = mock_dependencies

    # Arrange: Simulate the domain engine throwing a ValueError due to bad string formatting
    mock_engine.process_task_event.side_effect = ValueError("Malformed result_summary")

    event = TaskCompleted(task_name="evaluate_user_intent", status="success", result_summary="bad_data_no_separator")

    # Act: This should NOT raise an exception (which would crash the consumer)
    await on_task_completed(event)

    # Assert: We handled the error gracefully
    mock_logger.error.assert_called_once()
    assert "task_evaluation_domain_error" in mock_logger.error.call_args[0][0]

    # Ensure nothing was published
    mock_adapter.publish.assert_not_called()
