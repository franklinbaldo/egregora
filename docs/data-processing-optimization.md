# Data Processing Optimization Plan

Last updated: 2024-07-22

## Current Data Processing Patterns

The `egregora_v3` codebase utilizes Ibis for declarative queries against a DuckDB backend. Data is stored in a central `documents` table, where one column (`json_data`) contains a JSON blob of the full Pydantic model (`Entry` or `Document`).

Data retrieval methods in `DuckDBDocumentRepository` follow a common pattern:
1.  Execute an Ibis query to fetch metadata and the `json_data` blob.
2.  Load the results into a Pandas DataFrame.
3.  Iterate over the DataFrame rows using `iterrows()`.
4.  In each iteration, deserialize the JSON string into a Pydantic model.

## Identified Inefficiencies

-   **Inefficient Iteration:** The use of `pandas.DataFrame.iterrows()` in `DuckDBDocumentRepository.list` and `DuckDBDocumentRepository.get_entries_by_source` is a well-known performance anti-pattern. It is slow because it creates a new Series object for each row, adding significant overhead.
-   **Row-by-Row Deserialization:** While JSON deserialization is inherently a single-row operation, coupling it with `iterrows()` makes the entire data hydration process much slower than necessary.
-   **Iterative Sequence Fetching:** The `DuckDBStorageManager.next_sequence_values` method fetches sequence values iteratively in a `for` loop. This results in multiple round-trips to the database, creating a performance bottleneck when a large number of IDs are requested at once.

## Prioritized Optimizations

_None at the moment._

## Completed Optimizations

1.  **Vectorize DataFrame Processing:**
    -   **Target:** `DuckDBDocumentRepository.list` and `DuckDBDocumentRepository.get_entries_by_source`.
    -   **Impact:** Replaced slow `iterrows()` calls with efficient, direct iteration over DataFrame columns (Series). This is a standard, high-impact performance improvement that avoids the overhead of creating a Series object for every row, significantly speeding up data hydration for lists of documents. Correctness was ensured by establishing comprehensive tests before the refactor.
2.  **Vectorize Sequence Fetching:**
    -   **Target:** `DuckDBStorageManager.next_sequence_values`.
    -   **Impact:** Replaced an iterative `for` loop, which made `N` database calls, with a single vectorized query using `UNNEST(range(...))`. This reduces `N` database round-trips to one, significantly improving performance for batch ID generation. Correctness was verified with a new unit test before and after the optimization.

## Optimization Strategy

My strategy is to systematically eliminate imperative, row-by-row data processing patterns in favor of declarative and vectorized operations.

1.  **Prioritize Ibis:** Keep data processing within Ibis queries as much as possible.
2.  **Efficient Pandas Usage:** When data must be brought into memory as a DataFrame, use vectorized operations and avoid `iterrows()`.
3.  **Benchmark:** Ensure that optimizations provide a measurable performance improvement.
4.  **TDD:** Follow a strict Test-Driven Development process to ensure correctness is maintained.
