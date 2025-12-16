import pytest
import ibis
import pandas as pd
from datetime import datetime, UTC, timedelta
from egregora.database.elo_store import EloStore, EloRating, ELO_RATINGS_SCHEMA
from egregora.database.duckdb_manager import DuckDBStorageManager

@pytest.fixture
def memory_storage():
    """Create in-memory storage."""
    with DuckDBStorageManager(db_path=None) as storage:
        yield storage

def test_elo_store_append_only_updates(memory_storage):
    """Test that upserting multiple ratings results in append-only storage
    and get_rating retrieves the latest one."""

    store = EloStore(memory_storage)

    # Verify table empty
    assert memory_storage.row_count("elo_ratings") == 0

    # 1. First "upsert" (insert)
    t1 = datetime.now(UTC)
    r1 = EloRating("slug-1", 1500.0, 1, 1, 0, 0, t1, t1)
    store._upsert_rating(r1)

    assert memory_storage.row_count("elo_ratings") == 1
    fetched = store.get_rating("slug-1")
    assert fetched.rating == 1500.0
    assert fetched.comparisons == 1

    # 2. Second "upsert" (insert)
    t2 = t1 + timedelta(seconds=1)
    r2 = EloRating("slug-1", 1550.0, 2, 2, 0, 0, t2, t1)
    store._upsert_rating(r2)

    # Should append, not overwrite
    assert memory_storage.row_count("elo_ratings") == 2

    # get_rating should return latest
    fetched_latest = store.get_rating("slug-1")
    assert fetched_latest.rating == 1550.0
    assert fetched_latest.comparisons == 2
    assert fetched_latest.last_updated == t2

def test_elo_store_get_top_posts_latest_version(memory_storage):
    """Test get_top_posts filters for latest versions."""
    store = EloStore(memory_storage)

    base_time = datetime.now(UTC)

    # Post A: Rating 1500 -> 1600
    store._upsert_rating(EloRating("A", 1500.0, 1, 1, 0, 0, base_time, base_time))
    store._upsert_rating(EloRating("A", 1600.0, 2, 2, 0, 0, base_time + timedelta(seconds=10), base_time))

    # Post B: Rating 1400 -> 1300
    store._upsert_rating(EloRating("B", 1400.0, 1, 0, 1, 0, base_time, base_time))
    store._upsert_rating(EloRating("B", 1300.0, 2, 0, 2, 0, base_time + timedelta(seconds=10), base_time))

    # Post C: Rating 1550 (only one version)
    store._upsert_rating(EloRating("C", 1550.0, 1, 1, 0, 0, base_time, base_time))

    # Check raw rows
    assert memory_storage.row_count("elo_ratings") == 5

    # Get top posts
    top = store.get_top_posts(limit=3).execute()

    # Should have 3 rows (A, B, C unique)
    assert len(top) == 3

    # Expected order: A (1600), C (1550), B (1300)
    slugs = top["post_slug"].tolist()
    ratings = top["rating"].tolist()

    assert slugs == ["A", "C", "B"]
    assert ratings == [1600.0, 1550.0, 1300.0]

def test_load_parquet_integration(tmp_path):
    """Test load_parquet implementation via write_table."""
    storage = DuckDBStorageManager(db_path=None, checkpoint_dir=tmp_path)

    # Create simple table
    df = pd.DataFrame({"a": [1, 2]})
    t = ibis.memtable(df, name="source")

    # Write (replace)
    storage.write_table(t, "dest_table", mode="replace", checkpoint=True)

    # Verify
    res = storage.read_table("dest_table").execute()
    assert len(res) == 2

    # Write (append) - creates duplicates
    storage.write_table(t, "dest_table", mode="append", checkpoint=True)

    res_append = storage.read_table("dest_table").execute()
    assert len(res_append) == 4

    storage.close()
