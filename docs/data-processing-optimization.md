# Data Processing Optimization Plan

Last updated: 2024-07-25

## Current Data Processing Patterns

The `DuckDBDocumentRepository` in `src/egregora_v3/infra/repository/duckdb.py` uses a mix of Ibis for structured data queries and raw SQL for operations involving JSON fields. Client-side hydration loops are used to deserialize JSON data into Pydantic models after fetching it from the database.

## Identified Inefficiencies

1.  **Imperative JSON Filtering:** The `get_entries_by_source` method uses raw SQL (`json_extract_string`) to filter entries by a nested JSON field (`source.id`). This bypasses the Ibis compiler and relies on database-specific functions, making the code less portable and harder to maintain.
2.  **Client-Side Hydration:** The same method fetches a DataFrame of JSON strings and then iterates over it in Python to deserialize each row into an `Entry` object. This is inefficient as it moves a large amount of data from the database to the application and performs costly per-row processing in Python.

## Prioritized Optimizations

1.  **Refactor `get_entries_by_source` to use Ibis JSON functions.**
    *   **Rationale:** Modern Ibis has robust support for JSON operations. Using Ibis's `unpack` or `get_field` functions will allow the filtering to be expressed declaratively and executed entirely within the database engine. This will improve performance by reducing data transfer and leveraging DuckDB's optimized JSON processing.
    *   **Expected Impact:** High. This is a hot path for retrieving related entries, and the optimization will significantly reduce memory usage and execution time.

## Completed Optimizations

None yet.

## Optimization Strategy

My strategy is to systematically replace raw SQL and client-side processing loops with declarative Ibis expressions. The goal is to push as much of the data transformation logic as possible into the DuckDB engine, leveraging its vectorized execution and query optimization capabilities. All changes will be validated with TDD to ensure correctness.
