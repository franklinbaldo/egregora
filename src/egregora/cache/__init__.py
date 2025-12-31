"""Egregora Caching Subsystem.

This module provides a unified, tiered caching system for managing artifacts
of different types (e.g., assets, retrieval, synthesis) with granular
invalidation controls.

Key Components:
- `PipelineCache`: The main entry point for the caching system.
- `CacheTier`: An enumeration of the available cache tiers.
- `CacheBackend`: A protocol for implementing custom cache backends.
- `DiskCacheBackend`: A disk-based cache backend implementation.
"""

from egregora.cache.backends import CacheBackend, DiskCacheBackend
from egregora.cache.pipeline import CacheTier, PipelineCache

__all__ = ["CacheBackend", "CacheTier", "DiskCacheBackend", "PipelineCache"]
