# tests/unit/test_domain.py
import pytest
from datetime import datetime, timezone
from ana.domain.messages import ExecuteIONodeCommand, MessageHeader
from ana.domain.tuples import SPOCTuple


def test_command_serialization():
    """Test that DTOs can be serialized to JSON and deserialized back accurately."""
    header = MessageHeader(
        correlation_id="corr-123",
        source_component="test_runner"
    )
    cmd = ExecuteIONodeCommand(
        header=header,
        target_node_id="node_a",
        parameters={"fetch_limit": 100}
    )

    # Serialize to JSON string
    json_data = cmd.model_dump_json()

    # Deserialize back to object
    reconstructed_cmd = ExecuteIONodeCommand.model_validate_json(json_data)

    assert reconstructed_cmd.target_node_id == "node_a"
    assert reconstructed_cmd.parameters["fetch_limit"] == 100
    assert reconstructed_cmd.header.correlation_id == "corr-123"
    assert reconstructed_cmd.header.message_id == cmd.header.message_id


def test_tuple_immutability():
    """Test that Tuples are frozen and cannot be mutated."""
    tuple_obj = SPOCTuple(
        subject="Ana",
        predicate="is_type",
        object_="System",
        context="architecture"
    )

    with pytest.raises(Exception) as exc_info:
        tuple_obj.subject = "Bob"

    assert "Instance is frozen" in str(exc_info.value)


def test_tuple_hashability():
    """Test that Tuples can be used in sets due to being frozen/hashable."""
    tuple1 = SPOCTuple(subject="A", predicate="B", object_="C", context="D")
    tuple2 = SPOCTuple(subject="A", predicate="B", object_="C", context="D")
    tuple3 = SPOCTuple(subject="X", predicate="Y", object_="Z", context="W")

    # tuple1 and tuple2 have identical data, they should hash to the same value
    unique_tuples = {tuple1, tuple2, tuple3}

    # The set should only contain 2 items because tuple1 and tuple2 are duplicates
    assert len(unique_tuples) == 2
