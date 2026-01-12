from __future__ import annotations

import pytest

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.exceptions import TableNotFoundError


def test_get_columns_for_table_sql_injection_blocked():
    """Verify that SQL injection is prevented in get_columns_for_table."""
    storage = DuckDBStorageManager()

    # Create a dummy table so the database is not empty
    storage.execute_query("CREATE TABLE safe_table (id INT)")

    # Malicious table name attempting to inject a command
    # This payload tries to close the PRAGMA statement and start a new one.
    malicious_table_name = "safe_table); CREATE TABLE injection_successful (id INT); --"

    # The call should fail because the malicious table name is not found,
    # and it should NOT execute the injected CREATE TABLE statement.
    with pytest.raises(TableNotFoundError):
        storage.get_table_columns(malicious_table_name)

    # Verify that the injected command was NOT executed
    tables = storage.list_tables()
    assert "injection_successful" not in tables
    assert "safe_table" in tables

    storage.close()
