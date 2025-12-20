## 2025-12-18 - [CRITICAL] Supply Chain Risk in Jules Scheduler
**Vulnerability:** The `jules_scheduler.yml` workflow executed code from an external repository (`franklinbaldo/jules_scheduler`) using `@main`, allowing potential supply chain attacks if the external repository were compromised.
**Learning:** Using `@main` or `@latest` for external dependencies in CI/CD pipelines creates a window of vulnerability where malicious changes are immediately propagated to your environment.
**Prevention:** Pinned the `uvx` execution to a specific commit SHA (`4566f12...`) to ensure only verified code is executed. Future updates will require manual verification and SHA updates.

## 2025-12-18 - [CRITICAL] SQL Injection in DuckDB PRAGMA Statements
**Vulnerability:** The `get_table_columns` methods in both `SimpleDuckDBStorage` and `DuckDBStorageManager` constructed SQL queries using `f"PRAGMA table_info('{table_name}')"`. This allowed SQL injection via the `table_name` parameter because single quotes were used for interpolation without proper escaping, enabling attackers to break out of the string literal and execute arbitrary SQL commands (e.g., `DROP TABLE`).
**Learning:** DuckDB's `PRAGMA` statements do not support parameterized queries (e.g., `PRAGMA table_info(?)`), creating a trap for developers who might otherwise use parameters.
**Prevention:** Always use the `quote_identifier` utility to properly escape and double-quote identifiers when they must be interpolated into SQL strings. Never use single quotes for identifiers in f-strings.
