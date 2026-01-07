
import duckdb
import ibis
import pytest

from egregora.database.init import initialize_database
from egregora.database.schemas import UNIFIED_SCHEMA


@pytest.fixture
def memory_db():
    """Provides an in-memory DuckDB connection."""
    return ibis.duckdb.connect()

def test_initialize_database_creates_unified_table_only(memory_db):
    """Verify initialize_database creates only the 'documents' table with the correct schema."""
    # 1. Run initialization
    initialize_database(memory_db)

    # 2. Verify that ONLY the 'documents' table exists
    all_tables = sorted(memory_db.list_tables())
    assert all_tables == ["documents"], f"Expected only ['documents'], but found: {all_tables}"


    # 3. Verify 'documents' table has the correct schema
    # Check a few key columns from UNIFIED_SCHEMA
    table_info = memory_db.raw_sql("PRAGMA table_info('documents')").fetchall()
    column_names = {row[1] for row in table_info}
    assert "doc_type" in column_names
    assert "status" in column_names
    assert "extensions" in column_names
    assert "authors" in column_names  # from POSTS_SCHEMA
    assert "subject_uuid" in column_names  # from PROFILES_SCHEMA

    # 4. Verify the legacy view is not created
    with pytest.raises(duckdb.CatalogException):
        memory_db.raw_sql("SELECT * FROM documents_view")


def test_execute_sql_raises_for_invalid_connection():
    """Verify the internal _execute_sql raises AttributeError for an unsupported connection type."""
    # Import the internal function for direct testing
    from egregora.database.init import _execute_sql

    class InvalidConnection:
        pass

    with pytest.raises(AttributeError, match="does not support raw_sql or execute"):
        _execute_sql(InvalidConnection(), "SELECT 1")
