"""Tests for privacy configuration and functions."""

import ibis
import pytest

from egregora.privacy.anonymizer import anonymize_table


def test_anonymize_table_disabled():
    """Test anonymize_table skips when disabled."""
    # Create test table
    data = {
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize with enabled=False
    result = anonymize_table(table, enabled=False)

    # Should return unchanged
    result_data = result.execute()
    assert list(result_data["author_raw"]) == ["Alice", "Bob"]
    assert list(result_data["text"]) == ["Hello", "World"]


def test_anonymize_table_enabled():
    """Test anonymize_table anonymizes when enabled."""
    # Create test table
    data = {
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize with enabled=True (default)
    result = anonymize_table(table, enabled=True)

    # Should anonymize author_raw
    result_data = result.execute()
    assert list(result_data["author_raw"]) == ["uuid-alice", "uuid-bob"]


def test_anonymize_table_with_author_column():
    """Test anonymize_table handles 'author' column."""
    # Create test table with both author and author_raw
    data = {
        "author": ["Alice", "Bob"],
        "author_raw": ["Alice", "Bob"],
        "author_uuid": ["uuid-alice", "uuid-bob"],
        "text": ["Hello", "World"],
    }
    table = ibis.memtable(data)

    # Anonymize
    result = anonymize_table(table, enabled=True)

    # Both author and author_raw should be anonymized
    result_data = result.execute()
    assert list(result_data["author"]) == ["uuid-alice", "uuid-bob"]
    assert list(result_data["author_raw"]) == ["uuid-alice", "uuid-bob"]


def test_anonymize_table_missing_columns():
    """Test anonymize_table raises error for missing columns."""
    # Create table without required columns
    data = {"text": ["Hello", "World"]}
    table = ibis.memtable(data)

    # Should raise ValueError
    with pytest.raises(ValueError, match="missing required columns"):
        anonymize_table(table, enabled=True)
