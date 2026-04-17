# tests/integration/test_adapters.py
import pytest
import os
import shutil

from ana.adapters.local_storage import LocalResourceRepository
from ana.adapters.edgedb_graph import EdgeDBKnowledgeGraph
from ana.domain.tuples import SPOCTuple

# --- Local Storage Tests ---


@pytest.fixture
def temp_storage():
    """Fixture to provide a clean temporary directory for storage tests."""
    temp_dir = "storage/test_repo"
    repo = LocalResourceRepository(base_dir=temp_dir)
    yield repo
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_local_resource_repository(temp_storage):
    payload = b"Hello, Ana system."
    metadata = {"source": "test_script"}

    # Test Save
    uri = await temp_storage.save(payload, metadata)
    assert uri.startswith("local://")

    # Test Fetch
    fetched_payload = await temp_storage.fetch(uri)
    assert fetched_payload == payload


# --- EdgeDB Graph Tests ---
# Note: These tests require a running EdgeDB instance (`edgedb project init`).


@pytest.mark.asyncio
async def test_edgedb_idempotent_merge():
    graph = EdgeDBKnowledgeGraph()

    try:
        t1 = SPOCTuple(
            subject="ComponentA",
            predicate="depends_on",
            object_="ComponentB",
            context="architecture",
        )

        # First insert should succeed
        await graph.merge_tuples([t1])

        # Second insert of the exact same tuple should trigger `unless conflict`
        # and silently pass (idempotency requirement)
        await graph.merge_tuples([t1])

        # Verify it exists exactly once (querying raw EdgeQL)
        result = await graph.query(
            """
            select SPOCTuple { subject }
            filter .subject = 'ComponentA' and .predicate = 'depends_on';
        """,
            {},
        )

        assert len(result) == 1
        assert result[0]["subject"] == "ComponentA"

    finally:
        # Cleanup test data
        await graph.client.query("delete SPOCTuple filter .subject = 'ComponentA';")
        # CRUCIAL: Close the connection pool explicitly before the event loop is destroyed
        await graph.client.aclose()
