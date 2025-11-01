"""Tests for RankingStore schema and connection handling."""

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest

from egregora.core.database_schema import ELO_HISTORY_SCHEMA, ELO_RATINGS_SCHEMA
from egregora.knowledge.ranking.store import RankingStore


def test_schema_parity_ratings(tmp_path: Path):
    """Verify elo_ratings table matches ELO_RATINGS_SCHEMA."""
    store = RankingStore(rankings_dir=tmp_path)

    # Get table schema from DuckDB
    columns = store.conn.execute("DESCRIBE elo_ratings").fetchall()
    column_names = {col[0] for col in columns}
    column_types = {col[0]: col[1] for col in columns}

    # Check all schema columns exist
    assert set(ELO_RATINGS_SCHEMA.names) == column_names

    # Verify types (approximate mapping)
    assert "VARCHAR" in column_types["post_id"]
    assert "DOUBLE" in column_types["elo_global"]
    assert "BIGINT" in column_types["games_played"]
    assert "TIMESTAMP" in column_types["last_updated"]


def test_schema_parity_history(tmp_path: Path):
    """Verify elo_history table matches ELO_HISTORY_SCHEMA."""
    store = RankingStore(rankings_dir=tmp_path)

    # Get table schema from DuckDB
    columns = store.conn.execute("DESCRIBE elo_history").fetchall()
    column_names = {col[0] for col in columns}
    column_types = {col[0]: col[1] for col in columns}

    # Check all schema columns exist
    assert set(ELO_HISTORY_SCHEMA.names) == column_names

    # Verify types
    assert "VARCHAR" in column_types["comparison_id"]
    assert "TIMESTAMP" in column_types["timestamp"]
    assert "VARCHAR" in column_types["profile_id"]
    assert "VARCHAR" in column_types["post_a"]
    assert "VARCHAR" in column_types["post_b"]
    assert "VARCHAR" in column_types["winner"]
    assert "VARCHAR" in column_types["comment_a"]
    assert "BIGINT" in column_types["stars_a"]
    assert "VARCHAR" in column_types["comment_b"]
    assert "BIGINT" in column_types["stars_b"]


def test_standalone_connection(tmp_path: Path):
    """Test RankingStore with its own database file."""
    store = RankingStore(rankings_dir=tmp_path)

    assert store._owns_connection is True
    assert store.db_path == tmp_path / "rankings.duckdb"
    assert store.db_path.exists()

    # Verify tables exist
    tables = store.conn.execute("SHOW TABLES").fetchall()
    table_names = {row[0] for row in tables}
    assert "elo_ratings" in table_names
    assert "elo_history" in table_names


def test_shared_connection(tmp_path: Path):
    """Test RankingStore with shared DuckDB connection."""
    # Create shared connection
    db_path = tmp_path / "shared.duckdb"
    shared_conn = duckdb.connect(str(db_path))

    # Initialize store with shared connection
    store = RankingStore(connection=shared_conn)

    assert store._owns_connection is False
    assert store.db_path is None
    assert store.conn is shared_conn

    # Verify tables were created in shared connection
    tables = shared_conn.execute("SHOW TABLES").fetchall()
    table_names = {row[0] for row in tables}
    assert "elo_ratings" in table_names
    assert "elo_history" in table_names


def test_initialize_ratings(tmp_path: Path):
    """Test rating initialization."""
    store = RankingStore(rankings_dir=tmp_path)

    post_ids = ["post1", "post2", "post3"]
    inserted = store.initialize_ratings(post_ids)

    assert inserted == 3  # noqa: PLR2004

    # Verify ratings were created with defaults
    for post_id in post_ids:
        rating = store.get_rating(post_id)
        assert rating is not None
        assert rating["elo_global"] == 1500  # noqa: PLR2004
        assert rating["games_played"] == 0


def test_update_ratings(tmp_path: Path):
    """Test ELO rating updates."""
    store = RankingStore(rankings_dir=tmp_path)

    # Initialize posts
    store.initialize_ratings(["post1", "post2"])

    # Update ratings
    new_elo_a, new_elo_b = store.update_ratings("post1", "post2", 1516.0, 1484.0)

    assert new_elo_a == 1516.0  # noqa: PLR2004
    assert new_elo_b == 1484.0  # noqa: PLR2004

    # Verify updates persisted
    rating_a = store.get_rating("post1")
    rating_b = store.get_rating("post2")

    assert rating_a["elo_global"] == 1516.0  # noqa: PLR2004
    assert rating_a["games_played"] == 1
    assert rating_b["elo_global"] == 1484.0  # noqa: PLR2004
    assert rating_b["games_played"] == 1


def test_save_comparison(tmp_path: Path):
    """Test saving comparison history."""
    store = RankingStore(rankings_dir=tmp_path)

    comparison_data = {
        "comparison_id": "comp1",
        "timestamp": datetime.now(UTC),
        "profile_id": "profile123",
        "post_a": "post1",
        "post_b": "post2",
        "winner": "A",
        "comment_a": "Great post!",
        "stars_a": 5,
        "comment_b": "Good post.",
        "stars_b": 3,
    }

    store.save_comparison(comparison_data)

    # Verify comparison was saved
    history = store.get_all_history()
    df = history.execute()
    assert len(df) == 1
    assert df["comparison_id"][0] == "comp1"
    assert df["winner"][0] == "A"


def test_requires_dir_without_connection():
    """Test that rankings_dir is required when not providing connection."""
    with pytest.raises(ValueError, match="rankings_dir required"):
        RankingStore()
