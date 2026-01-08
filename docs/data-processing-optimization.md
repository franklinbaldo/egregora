# Data Processing Optimization Plan

Last updated: 2024-07-22

## Current Data Processing Patterns

The `egregora_v3` codebase utilizes Ibis for declarative queries against a DuckDB backend. Data is stored in a central `documents` table, where one column (`json_data`) contains a JSON blob of the full Pydantic model (`Entry` or `Document`).

Data retrieval methods in `DuckDBDocumentRepository` follow a common pattern:
1.  Execute an Ibis query to fetch metadata and the `json_data` blob.
2.  Load the results into a Pandas DataFrame.
3.  Iterate over the DataFrame rows using `iterrows()`.
4.  In each iteration, deserialize the JSON string into a Pydantic model.

The `egregora` codebase contains legacy patterns that involve iterating over data in Python instead of using declarative Ibis expressions.

## Identified Inefficiencies

-   **Inefficient Iteration:** The use of `pandas.DataFrame.iterrows()` in `DuckDBDocumentRepository.list` and `DuckDBDocumentRepository.get_entries_by_source` is a well-known performance anti-pattern. It is slow because it creates a new Series object for each row, adding significant overhead.
-   **Row-by-Row Deserialization:** While JSON deserialization is inherently a single-row operation, coupling it with `iterrows()` makes the entire data hydration process much slower than necessary.
-   **Imperative Logic in `MessageRepository`**: The `get_url_enrichment_candidates` and `get_media_enrichment_candidates` methods in `src/egregora/database/message_repository.py` use imperative Python loops to iterate over data batches. This row-by-row processing prevents the database from optimizing the data retrieval and aggregation, leading to unnecessary data transfer and slower execution.
-   **Iterative Sequence Fetching**: The `next_sequence_values` method in `src/egregora/database/duckdb_manager.py` fetches sequence values one at a time in a loop, creating significant overhead from repeated database calls, especially when a large number of values are requested.

## Prioritized Optimizations

1.  **Refactor `MessageRepository` to use Declarative Ibis Queries**: Convert the imperative loops in `get_url_enrichment_candidates` and `get_media_enrichment_candidates` into declarative Ibis expressions. This will involve using window functions (`ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` to efficiently find the first occurrence of each URL or media reference directly in the database.
2.  **Optimize Sequence Fetching in `DuckDBStorageManager`**: Modify `next_sequence_values` to generate multiple sequence values in a single, more efficient database query, reducing the number of round-trips to the database.

## Completed Optimizations

1.  **Vectorize DataFrame Processing:**
    -   **Target:** `DuckDBDocumentRepository.list` and `DuckDBDocumentRepository.get_entries_by_source`.
    -   **Impact:** Replaced slow `iterrows()` calls with efficient, direct iteration over DataFrame columns (Series). This is a standard, high-impact performance improvement that avoids the overhead of creating a Series object for every row, significantly speeding up data hydration for lists of documents. Correctness was ensured by establishing comprehensive tests before the refactor.

## Optimization Strategy

My strategy is to systematically eliminate imperative, row-by-row data processing patterns in favor of declarative and vectorized operations.

1.  **Prioritize Ibis:** Keep data processing within Ibis queries as much as possible.
2.  **Efficient Pandas Usage:** When data must be brought into memory as a DataFrame, use vectorized operations and avoid `iterrows()`.
3.  **Benchmark:** Ensure that optimizations provide a measurable performance improvement.
4.  **TDD:** Follow a strict Test-Driven Development process to ensure correctness is maintained.
