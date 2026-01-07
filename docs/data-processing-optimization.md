# Data Processing Optimization Plan

Last updated: 2024-07-22

## Current Data Processing Patterns

The `egregora_v3` codebase uses an Ibis-based repository pattern (`DuckDBDocumentRepository`) to interact with a DuckDB database. Data is stored in a single `documents` table with a JSON blob column (`json_data`) holding the serialized `Entry` or `Document` objects.

While most methods use the declarative Ibis API, some operations drop down to raw SQL for complex queries, particularly for filtering on nested JSON fields.

## Identified Inefficiencies

1.  **Raw SQL for JSON Filtering:**
    - **Location:** `src/egregora_v3/infra/repository/duckdb.py` in the `get_entries_by_source` method.
    - **Problem:** The method uses a raw SQL query with `json_extract_string` to filter entries by `source.id`. A comment suggests this is for reliability, but it bypasses the Ibis query optimizer, is less portable, and harder to maintain than a declarative Ibis expression.
    - **Evidence:**
      ```python
      sql = f"SELECT json_data, doc_type FROM {self.table_name} WHERE json_extract_string(json_data, '$.source.id') = ?"
      result = self.conn.con.execute(sql, [source_id]).fetch_df()
      ```

## Prioritized Optimizations

1.  **Refactor `get_entries_by_source` to use declarative Ibis API:**
    - **Rationale:** This is a high-impact, low-risk optimization. It aligns the entire repository with a declarative approach, improving maintainability and allowing the database to fully optimize the query. It serves as a clear example of the "let the database do the work" principle.
    - **Expected Impact:** Improved code clarity and maintainability. Potential for performance improvement as Ibis can generate a more optimized query plan than the raw string.

## Completed Optimizations

_None yet._

## Optimization Strategy

My strategy is to systematically eliminate raw SQL execution within the data repository and replace it with equivalent declarative Ibis expressions. All optimizations will follow a strict TDD process to ensure correctness is preserved. Each session will focus on a single, cohesive optimization bundle.
