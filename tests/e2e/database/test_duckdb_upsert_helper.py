"""Tests for DuckDBStorageManager replace_rows helper via EloStore usage."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import EloRating, EloStore


def test_replace_rows_prevents_duplicate_ratings(tmp_path: Path) -> None:
    """Replacing rows should update existing rating instead of duplicating."""

    db_path = tmp_path / "elo.duckdb"

    with DuckDBStorageManager(db_path=db_path) as storage:
        store = EloStore(storage)

        created_at = datetime.now(UTC)

        rating1 = EloRating(
            post_slug="post-1",
            rating=1500.0,
            comparisons=1,
            wins=1,
            losses=0,
            ties=0,
            last_updated=created_at,
            created_at=created_at,
        )
        store._upsert_rating(rating1)

        rating2 = EloRating(
            post_slug="post-1",
            rating=1550.0,
            comparisons=2,
            wins=2,
            losses=0,
            ties=0,
            last_updated=created_at,
            created_at=created_at,
        )
        store._upsert_rating(rating2)

        ratings = storage.execute_query("SELECT rating, comparisons FROM elo_ratings")

        assert len(ratings) == 1
        assert ratings[0][0] == 1550.0
        assert ratings[0][1] == 2
