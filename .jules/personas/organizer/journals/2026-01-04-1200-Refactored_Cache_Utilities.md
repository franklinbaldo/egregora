---
title: "🗂️ Refactored Cache Utilities"
date: 2026-01-04
author: "Organizer"
emoji: "🗂️"
type: journal
---

## 🗂️ 2026-01-04 - Summary

**Observation:** The `src/egregora/utils/cache.py` module was a "god module" containing two distinct caching components with different levels of abstraction: `EnrichmentCache` (a low-level, agent-specific cache) and `PipelineCache` (a high-level, orchestration-specific cache). This violated the Single Responsibility Principle and made the code harder to navigate.

**Action:**
- Relocated `PipelineCache` and its `CacheTier` enum to a new `src/egregora/orchestration/cache.py` file, co-locating it with the orchestration logic that uses it.
- Relocated `EnrichmentCache`, its helper function `make_enrichment_cache_key`, and its related exceptions to a new `src/egregora/agents/shared/` directory, clarifying its role as a shared utility for agents.
- Updated all consumer imports across the codebase to point to the new, more logical locations.
- Created comprehensive, co-located unit tests for both `PipelineCache` and `EnrichmentCache` to ensure the refactoring was safe and behavior-preserving.
- Deleted the now-empty `src/egregora/utils/cache.py` file, completing the cleanup.

**Reflection:** This refactoring successfully deconstructed a "god module" and improved the architectural clarity of the codebase. The TDD approach was critical for ensuring the move was safe. Generic `utils` directories are often a source of technical debt, and systematically identifying and refactoring domain-specific logic out of them is a high-impact organizational improvement. The `CacheKeyNotFoundError` exception remained in `utils` because it was also used by a generic backend utility, which highlights the need to check dependencies carefully to avoid introducing circular imports during refactoring.
