"""Tests for the git_commits schema (Git Cache)."""

import duckdb
import pytest

from egregora.database.init import initialize_database
from egregora.database.schemas import GIT_COMMITS_SCHEMA, create_table_if_not_exists


@pytest.fixture
def duckdb_conn():
    """Provides an in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


class TestGitCommitsSchema:
    """Test schema and indexes for git_commits."""

    def test_table_creation(self, duckdb_conn):
        """Verify git_commits table is created with correct columns."""
        # Act
        create_table_if_not_exists(duckdb_conn, "git_commits", GIT_COMMITS_SCHEMA)

        # Assert
        tables = [t[0] for t in duckdb_conn.execute("SHOW TABLES").fetchall()]
        assert "git_commits" in tables

        columns = duckdb_conn.execute("DESCRIBE git_commits").fetchall()
        col_names = [c[0] for c in columns]
        assert "repo_path" in col_names
        assert "commit_sha" in col_names
        assert "commit_timestamp" in col_names

    def test_index_creation(self, duckdb_conn):
        """Verify the compound index is created by initialize_database."""
        # Act: use initialize_database to test the full flow
        # initialize_database can handle raw connections, but we can wrap it to mock an Ibis backend
        initialize_database(duckdb_conn)

        # Assert
        # Check if index exists using duckdb_indexes system view
        duck_indexes = duckdb_conn.execute(
            "SELECT index_name FROM duckdb_indexes WHERE table_name='git_commits'"
        ).fetchall()
        index_names = [idx[0] for idx in duck_indexes]
        assert "idx_git_commits_lookup" in index_names

    def test_basic_query(self, duckdb_conn):
        """Verify we can insert and query."""
        create_table_if_not_exists(duckdb_conn, "git_commits", GIT_COMMITS_SCHEMA)

        duckdb_conn.execute("""
            INSERT INTO git_commits (repo_path, commit_sha, commit_timestamp, author, message)
            VALUES ('src/main.py', 'abc1234', '2023-01-01 10:00:00', 'me', 'init')
        """)

        res = duckdb_conn.execute(
            "SELECT commit_sha FROM git_commits WHERE repo_path = 'src/main.py'"
        ).fetchone()
        assert res[0] == "abc1234"
