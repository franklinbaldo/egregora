
import pytest
from egregora.database.duckdb_manager import temp_storage
from egregora.database.exceptions import SequenceNotFoundError

def test_sequence_parameterization_safety():
    """Verify sequence operations handle special characters safely."""
    with temp_storage() as storage:
        # 1. Test with a tricky sequence name containing quotes and SQL injection attempts
        # The name "seq'--drop" tries to close the quote and comment out the rest
        tricky_name = "seq'--drop"

        # This should handle the creation safely (using quote_identifier)
        storage.ensure_sequence(tricky_name, start=10)

        # Verify state
        state = storage.get_sequence_state(tricky_name)
        assert state.sequence_name == tricky_name
        assert state.start_value == 10

        # 2. Test next_sequence_values with the tricky name
        # This exercises the manual escaping logic (or parameterized query if fixed)
        values = storage.next_sequence_values(tricky_name, count=2)
        assert values == [10, 11]

        # 3. Test next_sequence_value
        val = storage.next_sequence_value(tricky_name)
        assert val == 12

def test_sequence_parameterization_regression():
    """Verify standard sequence operations work as expected."""
    with temp_storage() as storage:
        name = "simple_seq"
        storage.ensure_sequence(name)
        val = storage.next_sequence_value(name)
        assert val == 1
