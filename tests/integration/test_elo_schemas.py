"""Integration test for Elo schemas (ratings and history)."""

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


def test_elo_tables_and_indexes_created(duckdb_conn):
    """Verify that elo_ratings and comparison_history tables and their indexes are created."""
    # Act
    initialize_database(duckdb_conn)

    # Assert Tables
    result = duckdb_conn.execute("SHOW TABLES").fetchall()
    tables = {row[0] for row in result}
    assert "elo_ratings" in tables
    assert "comparison_history" in tables

    # Assert Indexes on elo_ratings
    result_ratings = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'elo_ratings'"
    ).fetchall()
    indexes_ratings = {row[0] for row in result_ratings}
    assert "idx_elo_ratings_slug" in indexes_ratings

    # Assert Indexes on comparison_history
    result_history = duckdb_conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'comparison_history'"
    ).fetchall()
    indexes_history = {row[0] for row in result_history}
    assert "idx_comparison_history_ts" in indexes_history
    assert "idx_comparison_history_post_a" in indexes_history
    assert "idx_comparison_history_post_b" in indexes_history


def test_elo_ratings_insertion(duckdb_conn):
    """Verify we can insert data into elo_ratings."""
    initialize_database(duckdb_conn)

    # Insert a dummy record
    ts = datetime.now(UTC)
    sql = """
    INSERT INTO elo_ratings (
        post_slug, rating, comparisons, wins, losses, ties, last_updated, created_at
    )
    VALUES ('my-post', 1510.5, 10, 5, 4, 1, ?, ?)
    """
    duckdb_conn.execute(sql, [ts, ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM elo_ratings").fetchall()
    assert len(result) == 1
    assert result[0][0] == "my-post"
    assert result[0][1] == 1510.5
    assert result[0][2] == 10


def test_comparison_history_insertion(duckdb_conn):
    """Verify we can insert data into comparison_history."""
    initialize_database(duckdb_conn)

    # Insert a dummy record
    ts = datetime.now(UTC)
    sql = """
    INSERT INTO comparison_history (
        comparison_id, post_a_slug, post_b_slug, winner,
        rating_a_before, rating_b_before, rating_a_after, rating_b_after,
        timestamp, reader_feedback
    )
    VALUES (
        'comp-123', 'post-a', 'post-b', 'a',
        1500.0, 1500.0, 1510.0, 1490.0,
        ?, '{"comment": "great"}'
    )
    """
    duckdb_conn.execute(sql, [ts])

    # Verify insertion
    result = duckdb_conn.execute("SELECT * FROM comparison_history").fetchall()
    assert len(result) == 1
    assert result[0][0] == "comp-123"
    assert result[0][1] == "post-a"
    assert result[0][3] == "a"
    assert result[0][9] == '{"comment": "great"}'
