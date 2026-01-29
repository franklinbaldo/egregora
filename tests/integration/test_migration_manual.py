"""Integration test for manual schema migration logic."""

import duckdb
import pytest
from egregora.database.init import initialize_database

@pytest.fixture
def duckdb_conn():
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()

def test_git_commits_migration(duckdb_conn):
    """Verify that old git_commits table gets updated with new columns."""

    # 1. Simulate OLD Schema
    # Create table WITHOUT new columns
    duckdb_conn.execute("""
        CREATE TABLE git_commits (
            repo_path VARCHAR,
            commit_sha VARCHAR,
            commit_timestamp TIMESTAMP WITH TIME ZONE,
            author VARCHAR,
            message VARCHAR
        )
    """)

    # Verify it doesn't have change_type
    # DuckDB raises BinderException or CatalogException if column missing
    try:
        duckdb_conn.execute("SELECT change_type FROM git_commits")
        pytest.fail("Column change_type should not exist yet")
    except Exception:
        pass

    # 2. Run Initialization (which should trigger migration)
    initialize_database(duckdb_conn)

    # 3. Verify New Columns Exist
    # This should verify both change_type and stats
    # We can check schema or just query
    result = duckdb_conn.execute("DESCRIBE git_commits").fetchall()
    columns = {row[0] for row in result}
    assert "change_type" in columns
    assert "stats" in columns

    # 4. Verify we can insert new data
    duckdb_conn.execute("""
        INSERT INTO git_commits (repo_path, commit_sha, change_type)
        VALUES ('p', 's', 'A')
    """)
    row = duckdb_conn.execute("SELECT change_type FROM git_commits").fetchall()[0]
    assert row[0] == 'A'
