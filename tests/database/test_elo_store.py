"""Tests for EloStore database operations."""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from egregora.agents.reader.elo import DEFAULT_ELO, calculate_elo_update
from egregora.database.duckdb_manager import DuckDBStorageManager
from egregora.database.elo_store import (
    EloStore,
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    # Use a temporary directory instead of file to avoid "not a valid DuckDB database" errors
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def storage(temp_db):
    """Create a DuckDBStorageManager instance with a temporary database."""
    return DuckDBStorageManager(db_path=temp_db)


@pytest.fixture
def elo_store(storage):
    """Create EloStore instance with a storage manager."""
    return EloStore(storage)


class TestEloStoreInitialization:
    """Test EloStore initialization and table creation."""

    def test_creates_database_file(self, temp_db):
        """Database file should be created."""
        storage = DuckDBStorageManager(db_path=temp_db)
        EloStore(storage)
        assert temp_db.exists()

    def test_creates_ratings_table(self, elo_store):
        """elo_ratings table should exist with correct schema."""
        tables = elo_store.storage.ibis_conn.list_tables()
        assert "elo_ratings" in tables

        table = elo_store.storage.ibis_conn.table("elo_ratings")
        schema = table.schema()

        # Check all required columns exist
        expected_columns = {
            "post_slug",
            "rating",
            "comparisons",
            "wins",
            "losses",
            "ties",
            "last_updated",
            "created_at",
        }
        assert set(schema.names) == expected_columns

    def test_creates_comparison_history_table(self, elo_store):
        """comparison_history table should exist with correct schema."""
        tables = elo_store.storage.ibis_conn.list_tables()
        assert "comparison_history" in tables

        table = elo_store.storage.ibis_conn.table("comparison_history")
        schema = table.schema()

        # Check all required columns exist
        expected_columns = {
            "comparison_id",
            "post_a_slug",
            "post_b_slug",
            "winner",
            "rating_a_before",
            "rating_b_before",
            "rating_a_after",
            "rating_b_after",
            "timestamp",
            "reader_feedback",
        }
        assert set(schema.names) == expected_columns

    def test_initialization_is_idempotent(self, temp_db):
        """Creating multiple stores with same DB should not error."""
        storage1 = DuckDBStorageManager(db_path=temp_db)
        EloStore(storage1)

        # Second initialization should work
        storage2 = DuckDBStorageManager(db_path=temp_db)
        store2 = EloStore(storage2)
        assert "elo_ratings" in store2.storage.ibis_conn.list_tables()
        assert "comparison_history" in store2.storage.ibis_conn.list_tables()


class TestGetRating:
    """Test retrieving ELO ratings."""

    def test_get_rating_for_new_post(self, elo_store):
        """New post should return default rating."""
        rating = elo_store.get_rating("new-post")

        assert rating.post_slug == "new-post"
        assert rating.rating == DEFAULT_ELO
        assert rating.comparisons == 0
        assert rating.wins == 0
        assert rating.losses == 0
        assert rating.ties == 0
        assert isinstance(rating.created_at, datetime)
        assert isinstance(rating.last_updated, datetime)

    def test_get_rating_for_existing_post(self, elo_store):
        """Existing post should return stored rating."""
        # Insert a rating
        now = datetime.now(UTC)
        elo_store._upsert_rating(
            post_slug="existing-post",
            rating=1600.0,
            comparisons=5,
            wins=3,
            losses=1,
            ties=1,
            last_updated=now,
            created_at=now,
        )

        # Retrieve it
        rating = elo_store.get_rating("existing-post")

        assert rating.post_slug == "existing-post"
        assert rating.rating == 1600.0
        assert rating.comparisons == 5
        assert rating.wins == 3
        assert rating.losses == 1
        assert rating.ties == 1

    def test_get_rating_returns_latest(self, elo_store):
        """Multiple ratings for same post should return latest."""
        now = datetime.now(UTC)

        # Insert first rating
        elo_store._upsert_rating(
            post_slug="post",
            rating=1500.0,
            comparisons=1,
            wins=0,
            losses=1,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        # Update rating (simulates upsert)
        elo_store._upsert_rating(
            post_slug="post",
            rating=1520.0,
            comparisons=2,
            wins=1,
            losses=1,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        rating = elo_store.get_rating("post")
        assert rating.rating == 1520.0
        assert rating.comparisons == 2
        assert rating.wins == 1


class TestUpdateRatings:
    """Test updating ratings after comparisons."""

    def test_update_ratings_for_new_posts(self, elo_store):
        """First comparison should create ratings for both posts."""
        # Calculate new ratings (both start at DEFAULT_ELO)
        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")

        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )

        # Check both posts have ratings
        rating_a = elo_store.get_rating("post-a")
        rating_b = elo_store.get_rating("post-b")

        assert rating_a.rating == new_a
        assert rating_a.comparisons == 1
        assert rating_a.wins == 1
        assert rating_a.losses == 0

        assert rating_b.rating == new_b
        assert rating_b.comparisons == 1
        assert rating_b.wins == 0
        assert rating_b.losses == 1

    def test_update_ratings_increments_stats(self, elo_store):
        """Comparisons should increment comparison counters."""
        # First comparison
        new_a1, new_b1 = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a1,
            rating_b_new=new_b1,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )

        # Second comparison (same posts)
        new_a2, new_b2 = calculate_elo_update(new_a1, new_b1, "b")
        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a2,
            rating_b_new=new_b2,
            winner="b",
            comparison_id=str(uuid.uuid4()),
        )

        rating_a = elo_store.get_rating("post-a")
        rating_b = elo_store.get_rating("post-b")

        assert rating_a.comparisons == 2
        assert rating_a.wins == 1
        assert rating_a.losses == 1

        assert rating_b.comparisons == 2
        assert rating_b.wins == 1
        assert rating_b.losses == 1

    def test_update_ratings_handles_ties(self, elo_store):
        """Ties should increment tie counter."""
        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "tie")

        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="tie",
            comparison_id=str(uuid.uuid4()),
        )

        rating_a = elo_store.get_rating("post-a")
        rating_b = elo_store.get_rating("post-b")

        assert rating_a.ties == 1
        assert rating_a.wins == 0
        assert rating_a.losses == 0

        assert rating_b.ties == 1
        assert rating_b.wins == 0
        assert rating_b.losses == 0

    def test_update_ratings_stores_reader_feedback(self, elo_store):
        """Reader feedback should be stored in comparison history."""
        feedback = '{"comment_a": "Great post!", "comment_b": "Good effort"}'

        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        comparison_id = str(uuid.uuid4())

        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="a",
            comparison_id=comparison_id,
            reader_feedback=feedback,
        )

        # Check comparison history
        history = elo_store.get_comparison_history().execute()
        assert len(history) == 1
        assert history.iloc[0]["reader_feedback"] == feedback

    def test_update_ratings_records_comparison_history(self, elo_store):
        """Each comparison should be recorded in history."""
        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        comparison_id = str(uuid.uuid4())

        elo_store.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="a",
            comparison_id=comparison_id,
        )

        history = elo_store.get_comparison_history().execute()
        assert len(history) == 1

        row = history.iloc[0]
        assert row["comparison_id"] == comparison_id
        assert row["post_a_slug"] == "post-a"
        assert row["post_b_slug"] == "post-b"
        assert row["winner"] == "a"
        assert row["rating_a_before"] == DEFAULT_ELO
        assert row["rating_b_before"] == DEFAULT_ELO
        assert row["rating_a_after"] == new_a
        assert row["rating_b_after"] == new_b


class TestGetTopPosts:
    """Test retrieving top-rated posts."""

    def test_get_top_posts_empty(self, elo_store):
        """Empty database should return empty result."""
        top_posts = elo_store.get_top_posts(limit=10).execute()
        assert len(top_posts) == 0

    def test_get_top_posts_sorts_by_rating(self, elo_store):
        """Posts should be sorted by rating descending."""
        now = datetime.now(UTC)

        # Insert posts with different ratings
        for slug, rating in [("low", 1400.0), ("high", 1600.0), ("medium", 1500.0)]:
            elo_store._upsert_rating(
                post_slug=slug,
                rating=rating,
                comparisons=5,
                wins=2,
                losses=2,
                ties=1,
                last_updated=now,
                created_at=now,
            )

        top_posts = elo_store.get_top_posts(limit=10).execute()
        assert len(top_posts) == 3
        assert top_posts.iloc[0]["post_slug"] == "high"
        assert top_posts.iloc[1]["post_slug"] == "medium"
        assert top_posts.iloc[2]["post_slug"] == "low"

    def test_get_top_posts_respects_limit(self, elo_store):
        """Should return at most limit posts."""
        now = datetime.now(UTC)

        # Insert 5 posts
        for i in range(5):
            elo_store._upsert_rating(
                post_slug=f"post-{i}",
                rating=1500.0 + i * 10,
                comparisons=5,
                wins=2,
                losses=2,
                ties=1,
                last_updated=now,
                created_at=now,
            )

        top_posts = elo_store.get_top_posts(limit=3).execute()
        assert len(top_posts) == 3

    def test_get_top_posts_filters_no_comparisons(self, elo_store):
        """Posts with 0 comparisons should not be included."""
        now = datetime.now(UTC)

        # Insert post with comparisons
        elo_store._upsert_rating(
            post_slug="compared",
            rating=1600.0,
            comparisons=5,
            wins=3,
            losses=2,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        # Insert post without comparisons
        elo_store._upsert_rating(
            post_slug="not-compared",
            rating=1700.0,  # Higher rating but no comparisons
            comparisons=0,
            wins=0,
            losses=0,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        top_posts = elo_store.get_top_posts(limit=10).execute()
        assert len(top_posts) == 1
        assert top_posts.iloc[0]["post_slug"] == "compared"


class TestGetComparisonHistory:
    """Test retrieving comparison history."""

    def test_get_comparison_history_empty(self, elo_store):
        """Empty database should return empty result."""
        history = elo_store.get_comparison_history().execute()
        assert len(history) == 0

    def test_get_comparison_history_all(self, elo_store):
        """Should return all comparisons without filter."""
        # Perform multiple comparisons
        for i in range(3):
            new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
            elo_store.update_ratings(
                post_a_slug=f"post-{i}",
                post_b_slug=f"post-{i + 1}",
                rating_a_new=new_a,
                rating_b_new=new_b,
                winner="a",
                comparison_id=str(uuid.uuid4()),
            )

        history = elo_store.get_comparison_history().execute()
        assert len(history) == 3

    def test_get_comparison_history_by_post(self, elo_store):
        """Should filter comparisons for specific post."""
        # Perform comparisons
        new_a1, new_b1 = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        elo_store.update_ratings(
            post_a_slug="post-1",
            post_b_slug="post-2",
            rating_a_new=new_a1,
            rating_b_new=new_b1,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )

        new_a2, new_b2 = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "b")
        elo_store.update_ratings(
            post_a_slug="post-2",
            post_b_slug="post-3",
            rating_a_new=new_a2,
            rating_b_new=new_b2,
            winner="b",
            comparison_id=str(uuid.uuid4()),
        )

        # Get history for post-2 (should appear in both)
        history = elo_store.get_comparison_history(post_slug="post-2").execute()
        assert len(history) == 2

        # Get history for post-1 (should appear in one)
        history = elo_store.get_comparison_history(post_slug="post-1").execute()
        assert len(history) == 1
        assert history.iloc[0]["post_a_slug"] == "post-1"

    def test_get_comparison_history_respects_limit(self, elo_store):
        """Should respect limit parameter."""
        # Perform multiple comparisons
        for i in range(5):
            new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
            elo_store.update_ratings(
                post_a_slug=f"post-{i}",
                post_b_slug=f"post-{i + 1}",
                rating_a_new=new_a,
                rating_b_new=new_b,
                winner="a",
                comparison_id=str(uuid.uuid4()),
            )

        history = elo_store.get_comparison_history(limit=3).execute()
        assert len(history) == 3

    def test_get_comparison_history_sorted_by_timestamp(self, elo_store):
        """History should be sorted by timestamp descending."""
        # Perform comparisons with slight delays
        for i in range(3):
            new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
            elo_store.update_ratings(
                post_a_slug=f"post-{i}",
                post_b_slug=f"post-{i + 1}",
                rating_a_new=new_a,
                rating_b_new=new_b,
                winner="a",
                comparison_id=f"comparison-{i}",
            )

        history = elo_store.get_comparison_history().execute()

        # Most recent should be first
        assert history.iloc[0]["comparison_id"] == "comparison-2"
        assert history.iloc[1]["comparison_id"] == "comparison-1"
        assert history.iloc[2]["comparison_id"] == "comparison-0"


class TestUpsertRating:
    """Test upserting rating records."""

    def test_upsert_creates_new_record(self, elo_store):
        """Upsert should create new record if none exists."""
        now = datetime.now(UTC)

        elo_store._upsert_rating(
            post_slug="new-post",
            rating=1550.0,
            comparisons=1,
            wins=1,
            losses=0,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        rating = elo_store.get_rating("new-post")
        assert rating.rating == 1550.0

    def test_upsert_updates_existing_record(self, elo_store):
        """Upsert should update existing record."""
        now = datetime.now(UTC)

        # Create initial record
        elo_store._upsert_rating(
            post_slug="post",
            rating=1500.0,
            comparisons=1,
            wins=0,
            losses=1,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        # Update record
        elo_store._upsert_rating(
            post_slug="post",
            rating=1520.0,
            comparisons=2,
            wins=1,
            losses=1,
            ties=0,
            last_updated=now,
            created_at=now,
        )

        rating = elo_store.get_rating("post")
        assert rating.rating == 1520.0
        assert rating.comparisons == 2

        # Verify only one record exists
        ratings_table = elo_store.storage.ibis_conn.table("elo_ratings")
        all_ratings = ratings_table.execute()
        post_ratings = all_ratings[all_ratings["post_slug"] == "post"]
        assert len(post_ratings) == 1


class TestDatabasePersistence:
    """Test that data persists across connections."""

    def test_ratings_persist_after_close(self, temp_db):
        """Ratings should persist after closing connection."""
        # Create store and add rating
        storage1 = DuckDBStorageManager(db_path=temp_db)
        store1 = EloStore(storage1)
        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        store1.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="a",
            comparison_id=str(uuid.uuid4()),
        )

        # Reopen and verify
        storage2 = DuckDBStorageManager(db_path=temp_db)
        store2 = EloStore(storage2)
        rating = store2.get_rating("post-a")
        assert rating.rating == new_a
        assert rating.comparisons == 1

    def test_history_persists_after_close(self, temp_db):
        """Comparison history should persist after closing connection."""
        # Create store and add comparison
        storage1 = DuckDBStorageManager(db_path=temp_db)
        store1 = EloStore(storage1)
        new_a, new_b = calculate_elo_update(DEFAULT_ELO, DEFAULT_ELO, "a")
        comparison_id = str(uuid.uuid4())
        store1.update_ratings(
            post_a_slug="post-a",
            post_b_slug="post-b",
            rating_a_new=new_a,
            rating_b_new=new_b,
            winner="a",
            comparison_id=comparison_id,
        )

        # Reopen and verify
        storage2 = DuckDBStorageManager(db_path=temp_db)
        store2 = EloStore(storage2)
        history = store2.get_comparison_history().execute()
        assert len(history) == 1
        assert history.iloc[0]["comparison_id"] == comparison_id
