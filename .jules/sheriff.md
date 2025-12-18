# Sheriff's Journal

## 2025-05-15 - DuckDB API Drift
**Crime:** Tests accessing private or removed methods (`execute`) on `DuckDBStorageManager`.
**Verdict:** Tests must use the public API (`_execute_sql` is internal, but maybe we need a public way to execute raw SQL for setup? or use Ibis).
