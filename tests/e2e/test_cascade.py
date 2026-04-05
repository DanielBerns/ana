# tests/e2e/test_cascade.py
import pytest
import asyncio
import httpx
import uuid

# Import your custom adapter instead of raw FastStream components
from shared.infrastructure import RabbitMQAdapter, RABBITMQ_URL_DEFAULT
from shared.events import ActionRequired

# Point these to your local Docker infrastructure
GATEWAY_URL = "http://127.0.0.1:8000/webhook/chat"
RABBITMQ_URL = RABBITMQ_URL_DEFAULT

@pytest.mark.asyncio
async def test_diagnostic_cascade_end_to_end():
    """
    Tests the full neurosymbolic cascade:
    Interface -> Controller -> NLP Actor -> Rules Engine -> Interface
    """
    # 1. Setup the Observer using YOUR custom adapter
    adapter = RabbitMQAdapter(RABBITMQ_URL)
    cascade_complete = asyncio.Event()
    received_action = None

    # Dynamically named queue so we eavesdrop without stealing the real app's messages
    observer_queue = f"e2e_observer_{uuid.uuid4().hex[:8]}"

    # Use your adapter's subscribe method, matching the production signature
    @adapter.subscribe(queue_name=observer_queue, routing_key="actions")
    async def observe_action(event: ActionRequired):
        nonlocal received_action
        received_action = event
        cascade_complete.set() # Signal that the cascade has reached the end

    # 2. Execute the Test
    # The async context manager automatically connects and starts consuming
    async with adapter.broker:

        # Step A: Trigger the Gateway
        async with httpx.AsyncClient() as client:
            test_user_id = "e2e_test_user"
            response = await client.post(
                GATEWAY_URL,
                json={"user_id": test_user_id, "message": "Initiate system diagnostic."},
                timeout=5.0
            )
            assert response.status_code == 200, "Gateway rejected the payload"
            correlation_id = response.json().get("correlation_id")

        # Step B: Wait for the system to process the cascade
        try:
            # We give Ana 5 seconds to complete the entire distributed thought process
            await asyncio.wait_for(cascade_complete.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("E2E Cascade timed out. The system did not emit an ActionRequired event.")

        # Step C: Assert the Final Output
        assert received_action is not None
        assert received_action.user_id == test_user_id
        assert received_action.correlation_id == correlation_id

        # Verify the SymbolicRuleEngine successfully evaluated the intent
        assert "Diagnostic verified" in received_action.payload
        assert "deterministic and online" in received_action.payload
