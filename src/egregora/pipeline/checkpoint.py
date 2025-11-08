"""Content-addressed checkpointing for deterministic pipeline resumption.

This module enables pipelines to skip expensive stages when:
1. Input data hasn't changed (same fingerprint)
2. Code version hasn't changed (same git commit)
3. Configuration hasn't changed (same config hash)

Checkpoints are content-addressed: SHA256(input + code + config) → output path.
This ensures deterministic resumption: same inputs always load same checkpoint.

Usage:
    from egregora.pipeline.checkpoint import (
        checkpoint_path,
        load_checkpoint,
        save_checkpoint,
        run_with_checkpointing,
    )

    # Generate checkpoint path
    cp_path = checkpoint_path(
        stage="enrichment",
        input_fingerprint="sha256:abc123",
        code_ref="a1b2c3d4",
        config_hash="sha256:def456",
    )

    # Load checkpoint if exists
    cached_result = load_checkpoint(cp_path)
    if cached_result is not None:
        print("Cache hit! Skipping stage...")
        return cached_result

    # Execute stage
    result = expensive_stage_function(input_table)

    # Save checkpoint for future runs
    save_checkpoint(cp_path, result)

    # Or use convenience wrapper
    result = run_with_checkpointing(
        stage_func=expensive_stage_function,
        stage="enrichment",
        input_table=input_table,
        cache_dir=Path(".egregora-cache/checkpoints"),
    )
"""

import hashlib
import pickle
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import ibis

T = TypeVar("T")


def get_config_hash(config: Any) -> str:
    """Generate SHA256 hash of configuration object.

    Args:
        config: Configuration object (must be picklable)

    Returns:
        SHA256 hash (format: "sha256:<hex>")

    Note:
        This uses pickle serialization, which may not be stable across
        Python versions. For production, consider using a more stable
        serialization format (e.g., JSON with sorted keys).

    """
    try:
        serialized = pickle.dumps(config, protocol=pickle.HIGHEST_PROTOCOL)
        hash_obj = hashlib.sha256(serialized)
        return f"sha256:{hash_obj.hexdigest()}"
    except (pickle.PicklingError, TypeError, AttributeError):
        # Fallback: hash string representation
        # FIXME: This is not stable (dict ordering, memory addresses)
        # AttributeError: lambda functions, local objects
        # TypeError: some built-in types
        # PicklingError: general pickle failures
        hash_obj = hashlib.sha256(str(config).encode("utf-8"))
        return f"sha256:{hash_obj.hexdigest()}"


def checkpoint_path(
    stage: str,
    input_fingerprint: str,
    code_ref: str | None = None,
    config_hash: str | None = None,
    cache_dir: Path = Path(".egregora-cache/checkpoints"),
) -> Path:
    """Generate content-addressed checkpoint path.

    The checkpoint path is deterministic: same inputs → same path.
    This enables cache invalidation when inputs change.

    Args:
        stage: Pipeline stage identifier (e.g., "enrichment")
        input_fingerprint: SHA256 of input data (from fingerprint_table)
        code_ref: Git commit SHA (optional, auto-detected if None)
        config_hash: SHA256 of config (optional)
        cache_dir: Base directory for checkpoints (default: .egregora-cache/checkpoints)

    Returns:
        Path to checkpoint file

    Example:
        >>> cp_path = checkpoint_path(
        ...     stage="enrichment",
        ...     input_fingerprint="sha256:abc123...",
        ...     code_ref="a1b2c3d4",
        ... )
        >>> print(cp_path)
        .egregora-cache/checkpoints/enrichment/abc123.../checkpoint.pkl

    """
    # Auto-detect code_ref if not provided
    if code_ref is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
            )
            code_ref = result.stdout.strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            code_ref = "unknown"

    # Create composite fingerprint: input + code + config
    composite_parts = [input_fingerprint]
    if code_ref:
        composite_parts.append(code_ref)
    if config_hash:
        composite_parts.append(config_hash)

    composite_fingerprint = hashlib.sha256(":".join(composite_parts).encode("utf-8")).hexdigest()

    # Generate hierarchical path: stage/composite_fingerprint/checkpoint.pkl
    # This structure allows:
    # - Easy cleanup by stage
    # - Content-addressed lookup
    # - Multiple versions per stage (different inputs/code/config)
    stage_dir = cache_dir / stage
    checkpoint_dir = stage_dir / composite_fingerprint[:16]  # First 16 chars (collision-resistant)
    checkpoint_file = checkpoint_dir / "checkpoint.pkl"

    return checkpoint_file


def load_checkpoint(path: Path) -> Any | None:
    """Load checkpoint from disk if it exists.

    Args:
        path: Path to checkpoint file (from checkpoint_path)

    Returns:
        Cached result if checkpoint exists, None otherwise

    Note:
        This uses pickle deserialization. Only load checkpoints from
        trusted sources (your own pipeline runs).

    """
    if not path.exists():
        return None

    try:
        with path.open("rb") as f:
            return pickle.load(f)
    except (pickle.UnpicklingError, EOFError, OSError):
        # Checkpoint corrupted or incompatible
        return None


def save_checkpoint(path: Path, result: Any) -> None:
    """Save checkpoint to disk.

    Args:
        path: Path to checkpoint file (from checkpoint_path)
        result: Result to cache (must be picklable)

    Raises:
        OSError: If directory creation or file write fails
        pickle.PicklingError: If result cannot be pickled

    """
    # Create parent directories
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write checkpoint atomically (write to temp, then rename)
    temp_path = path.with_suffix(".tmp")
    try:
        with temp_path.open("wb") as f:
            pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)

        # Atomic rename (POSIX systems only)
        temp_path.replace(path)
    except Exception:
        # Cleanup temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise


def run_with_checkpointing(
    stage_func: Callable[..., T],
    *,
    stage: str,
    input_table: ibis.Table | None = None,
    input_fingerprint: str | None = None,
    code_ref: str | None = None,
    config: Any = None,
    cache_dir: Path = Path(".egregora-cache/checkpoints"),
    **kwargs: Any,
) -> tuple[T, bool]:
    """Execute stage with automatic checkpointing.

    This wrapper:
    1. Computes input fingerprint (if not provided)
    2. Checks if checkpoint exists (cache lookup)
    3. If cache hit: return cached result
    4. If cache miss: execute stage_func, save checkpoint
    5. Returns (result, was_cached)

    Args:
        stage_func: Pipeline stage function to execute
        stage: Stage identifier (for checkpoint path)
        input_table: Input Ibis table (for fingerprinting, optional)
        input_fingerprint: Pre-computed fingerprint (optional, auto-computed if None)
        code_ref: Git commit SHA (optional, auto-detected)
        config: Configuration object (optional, for cache key)
        cache_dir: Checkpoint directory (default: .egregora-cache/checkpoints)
        **kwargs: Additional arguments to pass to stage_func

    Returns:
        (result, was_cached):
            - result: Stage function output
            - was_cached: True if loaded from checkpoint, False if executed

    Example:
        >>> result, was_cached = run_with_checkpointing(
        ...     stage_func=enrich_urls,
        ...     stage="enrichment",
        ...     input_table=privacy_table,
        ...     config=enrichment_config,
        ... )
        >>> if was_cached:
        ...     print("Cache hit! Skipped enrichment.")

    """
    # Compute input fingerprint if not provided
    if input_fingerprint is None and input_table is not None:
        from egregora.pipeline.runner import fingerprint_table

        input_fingerprint = fingerprint_table(input_table)
    elif input_fingerprint is None:
        # No input table and no fingerprint → use empty fingerprint
        input_fingerprint = "sha256:0" * 64

    # Compute config hash
    config_hash = None
    if config is not None:
        config_hash = get_config_hash(config)

    # Generate checkpoint path
    cp_path = checkpoint_path(
        stage=stage,
        input_fingerprint=input_fingerprint,
        code_ref=code_ref,
        config_hash=config_hash,
        cache_dir=cache_dir,
    )

    # Try loading checkpoint
    cached_result = load_checkpoint(cp_path)
    if cached_result is not None:
        return cached_result, True  # Cache hit

    # Cache miss: execute stage
    if input_table is not None:
        result = stage_func(input_table=input_table, **kwargs)
    else:
        result = stage_func(**kwargs)

    # Save checkpoint
    try:
        save_checkpoint(cp_path, result)
    except (pickle.PicklingError, OSError):
        # Log warning but don't fail (checkpointing is optional)
        # FIXME: Add proper logging when logfire/logging is configured
        pass

    return result, False  # Cache miss


def clear_checkpoints(
    stage: str | None = None,
    cache_dir: Path = Path(".egregora-cache/checkpoints"),
) -> int:
    """Clear checkpoints (cache invalidation).

    Args:
        stage: Stage identifier (optional, clears all if None)
        cache_dir: Checkpoint directory

    Returns:
        Number of checkpoint files deleted

    Example:
        >>> # Clear all enrichment checkpoints
        >>> count = clear_checkpoints(stage="enrichment")
        >>> print(f"Deleted {count} checkpoints")

        >>> # Clear all checkpoints
        >>> count = clear_checkpoints()

    """
    if not cache_dir.exists():
        return 0

    count = 0

    if stage is not None:
        # Clear specific stage
        stage_dir = cache_dir / stage
        if stage_dir.exists():
            for checkpoint_file in stage_dir.rglob("checkpoint.pkl"):
                checkpoint_file.unlink()
                count += 1
            # Remove empty directories
            for d in sorted(stage_dir.rglob("*"), reverse=True):
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
    else:
        # Clear all stages
        for checkpoint_file in cache_dir.rglob("checkpoint.pkl"):
            checkpoint_file.unlink()
            count += 1
        # Remove empty directories
        for d in sorted(cache_dir.rglob("*"), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    return count
