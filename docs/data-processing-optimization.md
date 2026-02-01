# Data Processing Optimization Plan

Last updated: 2026-03-02

## Current Data Processing Patterns

The `src/egregora/transformations/windowing.py` module is responsible for batching chat messages into windows for processing by the LLM. It supports windowing by message count, time duration, and byte size.

The current implementation for count and time-based windowing uses an inefficient iterative pattern:
- A Python `while` loop iterates, advancing an offset or a timestamp.
- Inside the loop, an Ibis query is executed (`.limit()`, `.filter()`, `.count().execute()`, `.min().execute()`, `.max().execute()`) for each window.
- This results in many small queries to the database (N+1 query problem), which is inefficient for DuckDB as it incurs overhead for each query.

The byte-based windowing is better, using an Ibis window function to calculate cumulative size, but it still falls back to a Python loop to generate the final windows.

## Identified Inefficiencies

1.  **`_window_by_count`:** Uses a `while` loop and `table.limit(offset=...)` to create windows. This is an imperative, iterative approach that executes multiple queries.
2.  **`_window_by_time`:** Uses a `while` loop that increments a `datetime` object and filters the table for each time slice. This is also an inefficient, iterative pattern.
3.  **`_window_by_bytes`:** While it uses a window function for cumulative sums, it still has a Python `while` loop that executes multiple queries to form the final windows. This can likely be improved.
4.  **Repeated Metadata Queries:** Helper functions like `_get_min_timestamp` and `_get_max_timestamp` are called within loops, causing redundant queries for metadata that could be fetched once.

## Prioritized Optimizations

- **Profile and Refactor `src/egregora/transformations/enrichment.py`.**
  - **Rationale:** Similar to windowing, enrichment might contain row-by-row operations that can be vectorized.
  - **Expected Impact:** Improved throughput for the initial data loading phase.

## Completed Optimizations

- **Refactored `_window_by_bytes` loop.**
  - **Date:** 2026-01-07
  - **Change:** Replaced the iterative `while` loop which executed N+1 queries with a "fetch-then-compute" strategy. The new implementation fetches metadata columns (row_number, ts, cumulative_bytes) into memory in a single query and computes window boundaries using Python `bisect`.
  - **Impact:** Benchmark showed ~16x speedup (8.22s -> 0.49s for 5000 messages). Reduced database queries from 3*N to 1.

- **Refactored `_window_by_time` to be declarative.**
  - **Date:** 2025-01-XX
  - **Change:** Replaced the iterative `while` loop (N+1 queries) with a single vectorized Ibis query. The new implementation assigns window indices to rows using timestamp arithmetic, handles overlaps via logic, and uses `unnest` + `group_by` to aggregate window counts in one pass.
  - **Impact:** Benchmark showed ~9.6x speedup (4.0s -> 0.4s for 334 windows). Reduced database queries from N+2 to 2.

- **Refactored `_window_by_count` to Fetch-then-Compute.**
  - **Date:** 2026-01-26
  - **Change:** Replaced the "declarative" Ibis loop (which still executed N aggregation queries) with a "Fetch-then-Compute" pattern. We now fetch all timestamps in a single O(1) query, compute window boundaries in Python (microseconds), and yield lazy table slices.
  - **Impact:** Benchmark showed **32x speedup** (3.2s -> 0.1s for 10,000 messages). Eliminated the hidden N+1 query cost of the previous implementation.

- **Refactored `split_window_into_n_parts` to Fetch-then-Compute.**
  - **Date:** 2026-02-12
  - **Change:** Replaced the imperative loop which executed N queries with a "Fetch-then-Compute" pattern. Now fetches all timestamps in one query and uses `bisect` to count messages in each partition locally.
  - **Impact:** Benchmark showed improvement from 1.19s to 0.85s for 50 splits. Reduced queries from N to 1.

- **Refactored `get_media_enrichment_candidates` to be Declarative.**
  - **Date:** 2026-02-27
  - **Change:** Replaced the imperative N+1 loop which iterated over row batches with a single declarative Ibis query using `regexp_extract_all` and `unnest`.
  - **Impact:** Benchmark showed **3x speedup** (1.13s -> 0.39s for 50k messages) and eliminated row-by-row Python processing.

- **Refactored `TaskStore.enqueue` to use Batching.**
  - **Date:** 2026-03-01
  - **Change:** Implemented `enqueue_batch` in `TaskStore` and updated `EnrichmentWorker` to collect tasks and insert them in a single batch operation, replacing the N+1 insertion loop.
  - **Impact:** Benchmark showed **835x speedup** (27,951ms -> 33ms for 1000 tasks).

- **Refactored `EnrichmentWorker` Media Updates to Nested Replace.**
  - **Date:** 2026-03-02
  - **Change:** Replaced the N+1 `UPDATE` loop for media reference replacements with a single batched `UPDATE` query using nested `replace()` calls and a `regexp_matches` filter.
  - **Impact:** Benchmark showed **6.8x speedup** (1.3s -> 0.19s for 50 updates on 100k rows).

## Optimization Strategy

My strategy is to systematically replace imperative, iterative data processing loops with declarative, vectorized Ibis expressions. The core principle is to "let the database do the work."

1.  **Identify Loops:** Find Python loops that execute Ibis queries.
2.  **Translate to Window Functions:** Rewrite the logic using Ibis window functions (`ibis.window`, `ibis.row_number`, etc.) or column-wise arithmetic to compute window identifiers for all rows at once.
3.  **Group and Yield:** After the data is tagged with window identifiers, use a single `group_by` or one final iteration over the pre-calculated results to yield the `Window` objects.
4.  **TDD:** For each optimization, I will first ensure tests exist. If not, I will write a test that captures the current behavior to ensure my refactoring does not introduce regressions.
