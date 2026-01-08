# Data Processing Optimization Plan

Last updated: 2024-07-25

## Current Data Processing Patterns

The codebase uses Ibis for database interactions, which is excellent. However, in `src/egregora/transformations/windowing.py`, the windowing logic for message streams is implemented using imperative Python loops. Functions like `_window_by_count` and `_window_by_time` iterate and execute multiple small queries (`.count()`, `.limit()`, `.aggregate()`) inside a `while` loop. This pattern pulls data back and forth between the Python process and the DuckDB engine, preventing the database from performing holistic optimizations.

## Identified Inefficiencies

1.  **Iterative Query Execution:** The primary inefficiency is the use of loops in Python to process data row-by-row or chunk-by-chunk instead of using vectorized, declarative Ibis expressions.
    - **Location:** `src/egregora/transformations/windowing.py`
    - **Functions:** `_window_by_count`, `_window_by_time`, `_window_by_bytes`.
    - **Evidence:** The code contains `while offset < total_count:` loops that repeatedly call `.execute()` on small slices of the main table. This is a known performance bottleneck in database-backed applications.

## Prioritized Optimizations

(None)

## Completed Optimizations

1.  **Attempted Refactoring of `windowing.py` (Reverted).**
    - **Date:** 2024-07-25
    - **Observation:** The `_window_by_count` and `_window_by_time` functions in `src/egregora/transformations/windowing.py` used imperative Python loops, which was identified as a potential performance bottleneck.
    - **Action:** I attempted to refactor these functions into a single, declarative Ibis query to improve performance.
    - **Result:** The declarative implementations for both functions failed to pass the existing test suite, producing incorrect window calculations. The logic for handling overlaps and steps proved to be too complex to express reliably in a simple declarative query. The changes were reverted in favor of the original, correct imperative implementation.
    - **Conclusion:** While the "declarative over imperative" principle is a good guideline, in this case, the imperative code is more correct and maintainable. The optimization was not worth the added complexity and risk of bugs.

## Optimization Strategy

My strategy for this codebase is to systematically identify and eliminate iterative, imperative data processing patterns and replace them with declarative, vectorized Ibis expressions. I will always follow a strict TDD methodology, leveraging existing tests or creating new ones to ensure that optimizations do not alter behavior. All changes will be measured and documented.
