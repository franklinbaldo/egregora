import ibis

from egregora.database.init import initialize_database


def test_documents_indexes_created(tmp_path):
    """Verify that indexes are created on the documents table."""
    # Setup temporary database
    db_path = tmp_path / "test.db"
    con = ibis.duckdb.connect(str(db_path))

    # Initialize
    initialize_database(con)

    # Verify indexes using raw DuckDB connection
    raw_con = con.con

    # Use system view duckdb_indexes()
    indexes = raw_con.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'documents'"
    ).fetchall()

    # Flatten results (list of tuples)
    index_names = [row[0] for row in indexes]

    assert "idx_documents_type" in index_names
    assert "idx_documents_slug" in index_names
    assert "idx_documents_created" in index_names
# Verified by Builder
