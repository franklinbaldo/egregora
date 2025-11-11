"""Unit tests for content-addressed checkpointing.

Tests:
- checkpoint_path() generates deterministic paths
- load_checkpoint() / save_checkpoint() round-trip
- run_with_checkpointing() wrapper (cache hits/misses)
- clear_checkpoints() cache invalidation
- get_config_hash() determinism
"""

from pathlib import Path

import ibis
import pytest

from egregora.pipeline.legacy.checkpoint import (
    checkpoint_path,
    clear_checkpoints,
    get_config_hash,
    load_checkpoint,
    run_with_checkpointing,
    save_checkpoint,
)


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create temporary checkpoint cache directory."""
    return tmp_path / "checkpoints"


@pytest.fixture
def sample_table() -> ibis.Table:
    """Create sample Ibis table for testing."""
    return ibis.memtable(
        [
            {"author": "Alice", "message": "Hello", "ts": "2025-01-01"},
            {"author": "Bob", "message": "Hi", "ts": "2025-01-02"},
        ]
    )


# ==============================================================================
# checkpoint_path() Tests
# ==============================================================================


def test_checkpoint_path_deterministic(temp_cache_dir: Path):
    """checkpoint_path() returns same path for same inputs."""
    path1 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        code_ref="a1b2c3d4",
        config_hash="sha256:def456",
        cache_dir=temp_cache_dir,
    )

    path2 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        code_ref="a1b2c3d4",
        config_hash="sha256:def456",
        cache_dir=temp_cache_dir,
    )

    assert path1 == path2


def test_checkpoint_path_different_inputs(temp_cache_dir: Path):
    """checkpoint_path() returns different paths for different inputs."""
    path1 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        cache_dir=temp_cache_dir,
    )

    path2 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:def456",
        cache_dir=temp_cache_dir,
    )

    assert path1 != path2


def test_checkpoint_path_different_code_ref(temp_cache_dir: Path):
    """checkpoint_path() returns different paths for different code versions."""
    path1 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        code_ref="commit1",
        cache_dir=temp_cache_dir,
    )

    path2 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        code_ref="commit2",
        cache_dir=temp_cache_dir,
    )

    assert path1 != path2


def test_checkpoint_path_different_config(temp_cache_dir: Path):
    """checkpoint_path() returns different paths for different configs."""
    path1 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        config_hash="sha256:config1",
        cache_dir=temp_cache_dir,
    )

    path2 = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        config_hash="sha256:config2",
        cache_dir=temp_cache_dir,
    )

    assert path1 != path2


def test_checkpoint_path_hierarchical_structure(temp_cache_dir: Path):
    """checkpoint_path() creates hierarchical directory structure."""
    path = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        cache_dir=temp_cache_dir,
    )

    # Path should be: cache_dir/stage/fingerprint_prefix/checkpoint.pkl
    assert path.parent.parent.name == "enrichment"
    assert path.name == "checkpoint.pkl"


# ==============================================================================
# save_checkpoint() / load_checkpoint() Tests
# ==============================================================================


def test_save_load_checkpoint_simple(temp_cache_dir: Path):
    """save_checkpoint() and load_checkpoint() round-trip simple objects."""
    cp_path = temp_cache_dir / "test" / "checkpoint.pkl"
    data = {"key": "value", "number": 42}

    # Save
    save_checkpoint(cp_path, data)
    assert cp_path.exists()

    # Load
    loaded = load_checkpoint(cp_path)
    assert loaded == data


def test_save_load_checkpoint_complex(temp_cache_dir: Path, sample_table: ibis.Table):
    """save_checkpoint() handles complex objects (lists, dicts, tables)."""
    cp_path = temp_cache_dir / "test" / "checkpoint.pkl"

    # Complex nested structure
    data = {
        "table": sample_table.execute(),  # pandas DataFrame
        "list": [1, 2, 3],
        "nested": {"a": {"b": {"c": "deep"}}},
    }

    # Save
    save_checkpoint(cp_path, data)

    # Load
    loaded = load_checkpoint(cp_path)
    assert loaded["list"] == [1, 2, 3]
    assert loaded["nested"]["a"]["b"]["c"] == "deep"
    assert len(loaded["table"]) == 2  # DataFrame has 2 rows


def test_load_checkpoint_nonexistent(temp_cache_dir: Path):
    """load_checkpoint() returns None for nonexistent checkpoint."""
    cp_path = temp_cache_dir / "nonexistent" / "checkpoint.pkl"
    loaded = load_checkpoint(cp_path)
    assert loaded is None


def test_save_checkpoint_creates_directories(temp_cache_dir: Path):
    """save_checkpoint() creates parent directories if they don't exist."""
    cp_path = temp_cache_dir / "deep" / "nested" / "path" / "checkpoint.pkl"
    assert not cp_path.parent.exists()

    save_checkpoint(cp_path, {"data": "test"})

    assert cp_path.exists()
    assert cp_path.parent.exists()


def test_save_checkpoint_atomic_write(temp_cache_dir: Path):
    """save_checkpoint() uses atomic write (temp file + rename)."""
    cp_path = temp_cache_dir / "test" / "checkpoint.pkl"

    # Save checkpoint
    save_checkpoint(cp_path, {"data": "test"})

    # Temp file should be cleaned up
    temp_path = cp_path.with_suffix(".tmp")
    assert not temp_path.exists()

    # Checkpoint should exist
    assert cp_path.exists()


# ==============================================================================
# get_config_hash() Tests
# ==============================================================================


def test_get_config_hash_deterministic():
    """get_config_hash() returns same hash for same config."""
    config = {"model": "gemini-1.5-flash", "temperature": 0.7}

    hash1 = get_config_hash(config)
    hash2 = get_config_hash(config)

    assert hash1 == hash2
    assert hash1.startswith("sha256:")


def test_get_config_hash_different_configs():
    """get_config_hash() returns different hashes for different configs."""
    config1 = {"model": "gemini-1.5-flash", "temperature": 0.7}
    config2 = {"model": "gemini-1.5-flash", "temperature": 0.8}

    hash1 = get_config_hash(config1)
    hash2 = get_config_hash(config2)

    assert hash1 != hash2


def test_get_config_hash_handles_unpicklable():
    """get_config_hash() falls back to str() for unpicklable objects."""
    # Lambda functions are not picklable
    config = {"func": lambda x: x + 1}

    # Should not raise, falls back to str() hash
    hash_val = get_config_hash(config)
    assert hash_val.startswith("sha256:")


# ==============================================================================
# run_with_checkpointing() Tests
# ==============================================================================


def test_run_with_checkpointing_cache_miss(temp_cache_dir: Path):
    """run_with_checkpointing() executes function on cache miss."""
    call_count = 0

    def stage_func(*, input_table=None, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return "result"

    result, was_cached = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        cache_dir=temp_cache_dir,
    )

    assert result == "result"
    assert was_cached is False
    assert call_count == 1  # Function was called


def test_run_with_checkpointing_cache_hit(temp_cache_dir: Path):
    """run_with_checkpointing() skips execution on cache hit."""
    call_count = 0

    def stage_func(*, input_table=None, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return "result"

    # First call: cache miss
    result1, was_cached1 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        cache_dir=temp_cache_dir,
    )

    assert result1 == "result"
    assert was_cached1 is False
    assert call_count == 1

    # Second call: cache hit
    result2, was_cached2 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        cache_dir=temp_cache_dir,
    )

    assert result2 == "result"
    assert was_cached2 is True
    assert call_count == 1  # Function NOT called again


def test_run_with_checkpointing_auto_fingerprint(
    temp_cache_dir: Path,
    sample_table: ibis.Table,
):
    """run_with_checkpointing() auto-computes fingerprint from input_table."""
    call_count = 0

    def stage_func(*, input_table, **kwargs):
        nonlocal call_count
        call_count += 1
        return input_table.mutate(processed=True)

    # First call (no fingerprint provided)
    _result1, was_cached1 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_table=sample_table,
        cache_dir=temp_cache_dir,
    )

    assert was_cached1 is False
    assert call_count == 1

    # Second call (same input_table, fingerprint auto-computed)
    _result2, was_cached2 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_table=sample_table,
        cache_dir=temp_cache_dir,
    )

    assert was_cached2 is True
    assert call_count == 1  # Cached


def test_run_with_checkpointing_different_config(temp_cache_dir: Path):
    """run_with_checkpointing() invalidates cache on config change."""
    call_count = 0

    def stage_func(*, input_table=None, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return "result"

    # First call with config1
    _result1, was_cached1 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        config={"temperature": 0.7},
        cache_dir=temp_cache_dir,
    )

    assert was_cached1 is False
    assert call_count == 1

    # Second call with config2 (different)
    _result2, was_cached2 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        config={"temperature": 0.8},  # Different config
        cache_dir=temp_cache_dir,
    )

    assert was_cached2 is False
    assert call_count == 2  # Cache invalidated


# ==============================================================================
# clear_checkpoints() Tests
# ==============================================================================


def test_clear_checkpoints_specific_stage(temp_cache_dir: Path):
    """clear_checkpoints() clears only specified stage."""
    # Create checkpoints for multiple stages
    save_checkpoint(temp_cache_dir / "stage1" / "abc" / "checkpoint.pkl", "data1")
    save_checkpoint(temp_cache_dir / "stage2" / "def" / "checkpoint.pkl", "data2")

    # Clear only stage1
    count = clear_checkpoints(stage="stage1", cache_dir=temp_cache_dir)

    assert count == 1
    assert not (temp_cache_dir / "stage1" / "abc" / "checkpoint.pkl").exists()
    assert (temp_cache_dir / "stage2" / "def" / "checkpoint.pkl").exists()


def test_clear_checkpoints_all_stages(temp_cache_dir: Path):
    """clear_checkpoints() clears all stages when stage=None."""
    # Create checkpoints for multiple stages
    save_checkpoint(temp_cache_dir / "stage1" / "abc" / "checkpoint.pkl", "data1")
    save_checkpoint(temp_cache_dir / "stage2" / "def" / "checkpoint.pkl", "data2")
    save_checkpoint(temp_cache_dir / "stage3" / "ghi" / "checkpoint.pkl", "data3")

    # Clear all
    count = clear_checkpoints(cache_dir=temp_cache_dir)

    assert count == 3
    assert not (temp_cache_dir / "stage1" / "abc" / "checkpoint.pkl").exists()
    assert not (temp_cache_dir / "stage2" / "def" / "checkpoint.pkl").exists()
    assert not (temp_cache_dir / "stage3" / "ghi" / "checkpoint.pkl").exists()


def test_clear_checkpoints_removes_empty_dirs(temp_cache_dir: Path):
    """clear_checkpoints() removes empty directories after deletion."""
    # Create checkpoint
    save_checkpoint(temp_cache_dir / "stage1" / "abc" / "checkpoint.pkl", "data")

    # Clear checkpoints
    clear_checkpoints(stage="stage1", cache_dir=temp_cache_dir)

    # Empty directories should be removed
    assert not (temp_cache_dir / "stage1" / "abc").exists()
    # FIXME: Currently doesn't remove stage1 directory itself
    # This is acceptable (parent dir cleanup is low priority)


def test_clear_checkpoints_nonexistent_cache_dir(temp_cache_dir: Path):
    """clear_checkpoints() returns 0 for nonexistent cache directory."""
    nonexistent = temp_cache_dir / "nonexistent"
    count = clear_checkpoints(cache_dir=nonexistent)
    assert count == 0


# ==============================================================================
# Integration Tests
# ==============================================================================


def test_checkpoint_invalidation_on_code_change(temp_cache_dir: Path):
    """Checkpoint is invalidated when code_ref changes."""
    call_count = 0

    def stage_func(*, input_table=None, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return f"result-{call_count}"

    # First call with commit1
    result1, was_cached1 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        code_ref="commit1",
        cache_dir=temp_cache_dir,
    )

    assert result1 == "result-1"
    assert was_cached1 is False
    assert call_count == 1

    # Second call with commit1 (cache hit)
    result2, was_cached2 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        code_ref="commit1",
        cache_dir=temp_cache_dir,
    )

    assert result2 == "result-1"
    assert was_cached2 is True
    assert call_count == 1  # Not called

    # Third call with commit2 (cache miss - code changed)
    result3, was_cached3 = run_with_checkpointing(
        stage_func=stage_func,
        stage="test-stage",
        input_fingerprint="sha256:test123",
        code_ref="commit2",  # Different code version
        cache_dir=temp_cache_dir,
    )

    assert result3 == "result-2"
    assert was_cached3 is False
    assert call_count == 2  # Called again


# ==============================================================================
# Garbage Collection Tests
# ==============================================================================


def test_gc_checkpoints_by_age_keeps_recent(temp_cache_dir: Path):
    """gc_checkpoints_by_age() keeps most recent checkpoints."""
    import time

    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_age

    # Create 10 checkpoints with different timestamps
    for i in range(10):
        save_checkpoint(temp_cache_dir / "stage1" / f"checkpoint{i}" / "checkpoint.pkl", f"data{i}")
        time.sleep(0.01)  # Ensure different mtimes

    # Keep only last 3
    count = gc_checkpoints_by_age(stage="stage1", keep_last=3, cache_dir=temp_cache_dir)

    assert count == 7  # Deleted 7 old checkpoints
    # Verify only 3 remain
    remaining = list((temp_cache_dir / "stage1").rglob("checkpoint.pkl"))
    assert len(remaining) == 3


def test_gc_checkpoints_by_age_all_stages(temp_cache_dir: Path):
    """gc_checkpoints_by_age() applies to all stages when stage=None."""
    import time

    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_age

    # Create checkpoints for multiple stages
    for stage_num in range(3):
        for i in range(5):
            save_checkpoint(
                temp_cache_dir / f"stage{stage_num}" / f"checkpoint{i}" / "checkpoint.pkl",
                f"data-{stage_num}-{i}",
            )
            time.sleep(0.01)

    # Keep last 2 per stage (all stages)
    count = gc_checkpoints_by_age(keep_last=2, cache_dir=temp_cache_dir)

    # Should delete 3 per stage (5 - 2) = 9 total
    assert count == 9

    # Verify each stage has 2 checkpoints
    for stage_num in range(3):
        remaining = list((temp_cache_dir / f"stage{stage_num}").rglob("checkpoint.pkl"))
        assert len(remaining) == 2


def test_gc_checkpoints_by_age_nonexistent_stage(temp_cache_dir: Path):
    """gc_checkpoints_by_age() returns 0 for nonexistent stage."""
    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_age

    count = gc_checkpoints_by_age(stage="nonexistent", keep_last=5, cache_dir=temp_cache_dir)
    assert count == 0


def test_gc_checkpoints_by_age_keep_all(temp_cache_dir: Path):
    """gc_checkpoints_by_age() keeps all when keep_last >= count."""
    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_age

    # Create 3 checkpoints
    save_checkpoint(temp_cache_dir / "stage1" / "a" / "checkpoint.pkl", "data1")
    save_checkpoint(temp_cache_dir / "stage1" / "b" / "checkpoint.pkl", "data2")
    save_checkpoint(temp_cache_dir / "stage1" / "c" / "checkpoint.pkl", "data3")

    # Keep last 10 (more than we have)
    count = gc_checkpoints_by_age(stage="stage1", keep_last=10, cache_dir=temp_cache_dir)

    assert count == 0  # Nothing deleted
    remaining = list((temp_cache_dir / "stage1").rglob("checkpoint.pkl"))
    assert len(remaining) == 3


def test_gc_checkpoints_by_size_under_limit(temp_cache_dir: Path):
    """gc_checkpoints_by_size() does nothing when already under limit."""
    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_size

    # Create small checkpoints
    save_checkpoint(temp_cache_dir / "stage1" / "a" / "checkpoint.pkl", "data")
    save_checkpoint(temp_cache_dir / "stage2" / "b" / "checkpoint.pkl", "data")

    # Set limit very high (1 GB)
    count = gc_checkpoints_by_size(max_size_bytes=1024**3, cache_dir=temp_cache_dir)

    assert count == 0  # Nothing deleted


def test_gc_checkpoints_by_size_evicts_lru(temp_cache_dir: Path):
    """gc_checkpoints_by_size() evicts least recently used checkpoints."""
    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_size

    # Create checkpoints with large data
    large_data = "x" * (1024 * 1024)  # 1 MB each

    save_checkpoint(temp_cache_dir / "stage1" / "a" / "checkpoint.pkl", large_data)
    save_checkpoint(temp_cache_dir / "stage1" / "b" / "checkpoint.pkl", large_data)
    save_checkpoint(temp_cache_dir / "stage1" / "c" / "checkpoint.pkl", large_data)

    # Set limit to ~2 MB (should keep 2, delete 1)
    count = gc_checkpoints_by_size(max_size_bytes=2 * 1024 * 1024, cache_dir=temp_cache_dir)

    assert count >= 1  # At least 1 deleted
    # Total cache should be under limit
    remaining_size = sum(p.stat().st_size for p in temp_cache_dir.rglob("checkpoint.pkl"))
    assert remaining_size <= 2 * 1024 * 1024


def test_gc_checkpoints_by_size_empty_cache(temp_cache_dir: Path):
    """gc_checkpoints_by_size() returns 0 for empty cache."""
    from egregora.pipeline.legacy.checkpoint import gc_checkpoints_by_size

    count = gc_checkpoints_by_size(max_size_bytes=1024, cache_dir=temp_cache_dir)
    assert count == 0


def test_get_cache_stats_empty(temp_cache_dir: Path):
    """get_cache_stats() returns zeros for empty cache."""
    from egregora.pipeline.legacy.checkpoint import get_cache_stats

    stats = get_cache_stats(cache_dir=temp_cache_dir)

    assert stats["total_size"] == 0
    assert stats["total_count"] == 0
    assert stats["stages"] == {}


def test_get_cache_stats_multiple_stages(temp_cache_dir: Path):
    """get_cache_stats() returns per-stage breakdown."""
    from egregora.pipeline.legacy.checkpoint import get_cache_stats

    # Create checkpoints for multiple stages
    save_checkpoint(temp_cache_dir / "stage1" / "a" / "checkpoint.pkl", "data1" * 100)
    save_checkpoint(temp_cache_dir / "stage1" / "b" / "checkpoint.pkl", "data2" * 100)
    save_checkpoint(temp_cache_dir / "stage2" / "c" / "checkpoint.pkl", "data3" * 200)

    stats = get_cache_stats(cache_dir=temp_cache_dir)

    # Verify total counts
    assert stats["total_count"] == 3
    assert stats["total_size"] > 0

    # Verify per-stage breakdown
    assert "stage1" in stats["stages"]
    assert "stage2" in stats["stages"]
    assert stats["stages"]["stage1"]["count"] == 2
    assert stats["stages"]["stage2"]["count"] == 1


def test_get_cache_stats_nonexistent_dir(temp_cache_dir: Path):
    """get_cache_stats() returns zeros for nonexistent directory."""
    from egregora.pipeline.legacy.checkpoint import get_cache_stats

    nonexistent = temp_cache_dir / "nonexistent"
    stats = get_cache_stats(cache_dir=nonexistent)

    assert stats["total_size"] == 0
    assert stats["total_count"] == 0
    assert stats["stages"] == {}
