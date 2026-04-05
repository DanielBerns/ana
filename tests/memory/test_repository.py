import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Adjust these imports to match your actual project structure
from memory.domain.models import Base, EventLog, Entity, NamedGraph, Quad
from memory.infrastructure.repository import MemoryRepository

# --- 1. Database Fixtures ---

@pytest_asyncio.fixture
async def db_session():
    """Spins up an isolated, in-memory SQLite database for each test."""
    # Use SQLite async driver instead of Postgres
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with AsyncSessionLocal() as session:
        yield session  # Provide the session to the test

    # Teardown
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
def repo(db_session: AsyncSession):
    """Provides a fresh MemoryRepository instance wired to the test DB."""
    return MemoryRepository(db_session)


# --- 2. Deterministic Ledger Tests ---

@pytest.mark.asyncio
async def test_log_event_and_get_history(repo: MemoryRepository):
    # Act: Log two sequential events
    await repo.log_event("corr-001", "UserPromptReceived", {"text": "Hello"})
    await repo.log_event("corr-001", "ContextRequested", {"query": "Hello"})

    # Act: Retrieve history
    history = await repo.get_recent_history(limit=5)

    # Assert
    assert len(history) == 2
    # Ensure chronological ordering (oldest first in the returned list, based on your repo logic)
    assert history[0]["text"] == "Hello"
    assert "query" in history[1]

# --- 3. Knowledge Graph (Node & Context) Tests ---

@pytest.mark.asyncio
async def test_ensure_graph_exists_is_idempotent(repo: MemoryRepository):
    # Act: Create it once
    graph1 = await repo.ensure_graph_exists("session:001", "Test Session")
    # Act: Create it again
    graph2 = await repo.ensure_graph_exists("session:001", "Test Session")

    # Assert
    assert graph1.id == "session:001"
    assert graph1.id == graph2.id

@pytest.mark.asyncio
async def test_ensure_entity_exists(repo: MemoryRepository):
    entity = await repo.ensure_entity_exists("user:123", "Operator", "Daniel")

    assert entity.id == "user:123"
    assert entity.entity_type == "Operator"
    assert entity.name == "Daniel"

# --- 4. Quad-Store Assertion Tests ---

@pytest.mark.asyncio
async def test_assert_quad_with_literal_object(repo: MemoryRepository):
    # Arrange: Setup the required Subject and Graph
    await repo.ensure_entity_exists("concept:sky", "Concept", "Sky")
    await repo.ensure_graph_exists("source:general_knowledge")

    # Act: Assert the fact
    quad = await repo.assert_quad(
        subject_id="concept:sky",
        predicate="has_color",
        object_literal_value="Blue",
        graph_id="source:general_knowledge",
        correlation_id="corr-test"
    )

    # Assert
    assert quad.subject_id == "concept:sky"
    assert quad.predicate == "has_color"
    assert quad.object_literal_value == "Blue"
    assert quad.object_entity_id is None

@pytest.mark.asyncio
async def test_assert_quad_with_entity_object(repo: MemoryRepository):
    # Arrange: Setup Subject, Object Entity, and Graph
    await repo.ensure_entity_exists("person:alice", "Person", "Alice")
    await repo.ensure_entity_exists("person:bob", "Person", "Bob")
    await repo.ensure_graph_exists("context:social")

    # Act: Assert relationship Alice -> knows -> Bob
    quad = await repo.assert_quad(
        subject_id="person:alice",
        predicate="knows",
        object_entity_id="person:bob",
        graph_id="context:social",
        correlation_id="corr-test"
    )

    # Assert
    assert quad.object_entity_id == "person:bob"
    assert quad.object_literal_value is None

@pytest.mark.asyncio
async def test_assert_quad_raises_error_on_invalid_objects(repo: MemoryRepository):
    # Act & Assert: Try passing BOTH a literal and an entity
    with pytest.raises(ValueError, match="exactly one object"):
        await repo.assert_quad(
            subject_id="sub",
            predicate="pred",
            object_entity_id="obj_id",
            object_literal_value="literal_value",
            graph_id="graph",
            correlation_id="corr"
        )

    # Act & Assert: Try passing NEITHER
    with pytest.raises(ValueError, match="exactly one object"):
        await repo.assert_quad(
            subject_id="sub",
            predicate="pred",
            graph_id="graph",
            correlation_id="corr"
        )
