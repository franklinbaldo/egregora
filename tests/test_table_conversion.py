"""Test table conversion for command processing.

This test reproduces the bug where ibis tables can't be converted to lists.
"""
import ibis
import pytest
from ibis.expr.types import Table as IbisTable


def test_ibis_table_to_list_fails_with_direct_call():
    """Reproduce the bug: ibis tables can't be converted with list()."""
    # Create a simple ibis table
    data = [
        {"id": 1, "text": "hello", "author_uuid": "user1"},
        {"id": 2, "text": "world", "author_uuid": "user2"},
    ]
    table = ibis.memtable(data)
    
    # This should be an ibis table
    assert isinstance(table, IbisTable)
    
    # This will FAIL - ibis tables are not iterable
    with pytest.raises(TypeError, match="'Table' object is not iterable"):
        list(table)


def test_ibis_table_has_no_execute_method():
    """Ibis tables don't have .execute() - they ARE expressions."""
    data = [{"id": 1, "text": "test"}]
    table = ibis.memtable(data)
    
    # .execute() is NOT a method on the table
    assert not hasattr(table, "execute")


def test_ibis_table_conversion_correct_way():
    """Show the correct way to convert ibis tables to lists."""
    data = [
        {"id": 1, "text": "hello", "author_uuid": "user1"},
        {"id": 2, "text": "world", "author_uuid": "user2"},
    ]
    table = ibis.memtable(data)
    
    # Method 1: to_pylist() - NOT to_pydict()!
    # But this doesn't exist on ibis tables either
    
    # Method 2: to_pandas() then to_dict('records')
    df = table.to_pandas()
    records = df.to_dict('records')
    assert len(records) == 2
    assert records[0]["text"] == "hello"
    
    # Method 3: Use ibis-native methods
    # table.to_pyarrow() exists and returns arrow table
    arrow_table = table.to_pyarrow()
    records_alt = arrow_table.to_pylist()
    assert len(records_alt) == 2
    assert records_alt[0]["text"] == "hello"


def test_correct_table_conversion():
    """Test the correct way we should convert tables."""
    data = [
        {"id": 1, "text": "/egregora avatar", "author_uuid": "user1"},
        {"id": 2, "text": "normal message", "author_uuid": "user2"},
    ]
    table = ibis.memtable(data)
    
    # CORRECT WAY: to_pyarrow().to_pylist()
    messages_list = table.to_pyarrow().to_pylist()
    
    assert len(messages_list) == 2
    assert isinstance(messages_list, list)
    assert all(isinstance(m, dict) for m in messages_list)
    assert messages_list[0]["text"] == "/egregora avatar"
