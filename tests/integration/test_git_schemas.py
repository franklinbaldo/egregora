"""Integration test for Git Context schemas (commits and refs)."""

from datetime import UTC, datetime

import duckdb
import pytest

from egregora.database.init import initialize_database


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


def test_git_tables_and_indexes_created(duckdb_conn):
    """Verify that git_commits and git_refs tables and their indexes are created."""
    # Act
    initialize_database(duckdb_conn)

    # Assert Tables
    result = duckdb_conn.execute("SHOW TABLES").fetchall()
    tables = {row[0] for row in result}
    assert "git_commits" in tables
    assert "git_refs" in tables

    # Assert Indexes on git_commits
    result_commits = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'git_commits'"
    ).fetchall()
    indexes_commits = {row[0] for row in result_commits}
    # Note: duckdb_indexes might not show implicit indexes or might name them differently,
    # but create_index names them explicitly.
    assert "idx_git_commits_lookup" in indexes_commits

    # Assert Indexes on git_refs
    result_refs = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'git_refs'"
    ).fetchall()
    indexes_refs = {row[0] for row in result_refs}
    assert "idx_git_refs_name" in indexes_refs
    assert "idx_git_refs_sha" in indexes_refs


def test_git_commits_insertion(duckdb_conn):
    """Verify we can insert data into git_commits."""
    initialize_database(duckdb_conn)

    # Insert a dummy record
    ts = datetime.now(UTC)
    sql = """
    INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, author, message)
    VALUES ('src/main.py', 'abc1234', ?, 'Visionary', 'Initial commit')
    """
    duckdb_conn.execute(sql, [ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM git_commits").fetchall()
    assert len(result) == 1
    assert result[0][0] == "src/main.py"
    assert result[0][1] == "abc1234"


def test_git_refs_insertion(duckdb_conn):
    """Verify we can insert data into git_refs."""
    initialize_database(duckdb_conn)

    # Insert a dummy record
    sql = """
    INSERT INTO git_refs (ref_name, commit_sha, is_tag, is_remote)
    VALUES ('refs/heads/main', 'def5678', false, false)
    """
    duckdb_conn.execute(sql)

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM git_refs").fetchall()
    assert len(result) == 1
    assert result[0][0] == "refs/heads/main"
    assert result[0][2] is False
