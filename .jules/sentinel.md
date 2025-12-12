## 2025-12-12 - [Secure SQL Construction for DuckDB]
**Vulnerability:** The `replace_rows` method in `DuckDBStorageManager` accepted a raw `where_clause` string, which was directly interpolated into a `DELETE` statement. Although current usage was safe, this design invited SQL injection vulnerabilities if user input were ever passed to it.
**Learning:** Even internal helper methods should enforce safety by design. Accepting structured data (e.g., a dictionary of keys) and building the query programmatically with `quote_identifier` and parameters eliminates the risk class entirely.
**Prevention:**
1.  Avoid APIs that accept partial SQL strings (like `where_clause`).
2.  Use structured inputs (dicts/lists) to generate WHERE clauses dynamically and safely.
3.  Always quote identifiers and parameterize values.
