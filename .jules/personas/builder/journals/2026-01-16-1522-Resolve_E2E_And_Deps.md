---
title: "🏗️ Resolve E2E Test Failures and Dependency Issues"
date: 2026-01-16T15:22
---

## Observation
The E2E tests for PR #2561 were failing due to multiple issues:
1.  **Usage Errors (SystemExit 2):** Tests invoking the `write` command were failing because the arguments were constructed incorrectly. The subcommand `write` was missing, and options were mixed with positional arguments in a way that confused the parser.
2.  **Dependency Conflicts:** A conflict between `pandas>=2.3.0` and `ibis-framework` caused schema mismatch errors (`ValueError: schema names don't match input data columns`) during data execution.
3.  **Connection Errors:** Downgrading `ibis-framework` to 10.0.0 introduced connection string parsing errors (`ValueError: Don't know how to connect to...`), necessitating an upgrade back to 11.0.0.

## Action
1.  **Fixed Test Helpers:** Updated `build_write_command_args` in `tests/e2e/test_config.py` to prepend the `write` subcommand and ensure positional arguments appear *after* options.
2.  **Pinned Dependencies:** Updated `pyproject.toml` to pin `pandas<2.3.0` (resolving the schema error) and `ibis-framework[duckdb]==11.0.0` (ensuring correct DuckDB connection handling).
3.  **Verified Fixes:** Confirmed that `egregora write` runs past the initial parsing stage and that relevant E2E tests now pass (or fail with expected application errors rather than usage errors).

## Reflection
This session underscored the importance of precise CLI argument ordering when programmatically invoking Typer/Click apps. It also highlighted the fragility of the data stack (`pandas`/`ibis`/`duckdb`), where minor version upgrades in transitive dependencies can break core functionality. Pinning versions is a necessary stabilizer.
