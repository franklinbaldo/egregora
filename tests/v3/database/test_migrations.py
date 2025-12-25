
import duckdb
import ibis
import ibis.expr.datatypes as dt
import pytest

from egregora.database.migrations import migrate_documents_table
from egregora.database.ir_schema import UNIFIED_SCHEMA

# Define a legacy schema that is a subset of the UNIFIED_SCHEMA
# This simulates the state of the database before the V3 migration.
LEGACY_SCHEMA = ibis.schema(
    {
        "id": dt.string,
        "title": dt.string,
        "updated": dt.timestamp(timezone="UTC"),
        "published": dt.timestamp(timezone="UTC", nullable=True),
        "links": dt.json,
        "authors": dt.json,
        "contributors": dt.json,
        "categories": dt.json,
        "summary": dt.string,
        "content": dt.string,
        "source": dt.json,
        "in_reply_to": dt.json,
    }
)


@pytest.fixture
def legacy_db_conn():
    """Provides an in-memory DuckDB connection with a legacy 'documents' table."""
    conn = duckdb.connect(":memory:")

    # Create a table with the old schema
    columns_sql = ", ".join(
        f"{name} VARCHAR" for name in LEGACY_SCHEMA.names
    )
    conn.execute(f"CREATE TABLE documents ({columns_sql})")

    # Insert a dummy row
    conn.execute("INSERT INTO documents (id, title) VALUES ('test-id', 'Test Title')")

    yield conn

    conn.close()


def test_migrate_documents_table_adds_missing_columns(legacy_db_conn):
    """
    Tests that migrate_documents_table correctly adds the new V3 columns
    to a legacy 'documents' table.
    """
    # 1. (Pre-migration) Assert that a new column does not exist.
    with pytest.raises(duckdb.BinderException):
        legacy_db_conn.execute("SELECT doc_type FROM documents")

    # 2. Run the migration
    migrate_documents_table(legacy_db_conn)

    # 3. (Post-migration) Assert that all new columns now exist.
    result = legacy_db_conn.execute("DESCRIBE documents").fetchall()
    existing_columns = {row[0] for row in result}

    assert "doc_type" in existing_columns
    assert "status" in existing_columns
    assert "extensions" in existing_columns
    assert "internal_metadata" in existing_columns

    # 4. Verify data integrity and default values
    data = legacy_db_conn.execute("SELECT * FROM documents").fetchone()
    columns_map = {col: i for i, col in enumerate(existing_columns)}

    # Can't guarantee column order, so fetch by name after getting the result tuple
    result_df = legacy_db_conn.execute("SELECT * FROM documents").fetchdf()

    assert result_df['id'][0] == 'test-id'
    assert result_df['title'][0] == 'Test Title'
    assert result_df['doc_type'][0] == 'post'
    assert result_df['status'][0] == 'published'


def test_migrate_documents_table_is_idempotent(legacy_db_conn):
    """
    Tests that running the migration multiple times does not cause errors.
    """
    # Run migration the first time
    migrate_documents_table(legacy_db_conn)

    # Get schema after first run
    result1 = legacy_db_conn.execute("DESCRIBE documents").fetchall()

    # Run migration a second time
    migrate_documents_table(legacy_db_conn)

    # Get schema after second run
    result2 = legacy_db_conn.execute("DESCRIBE documents").fetchall()

    assert result1 == result2
