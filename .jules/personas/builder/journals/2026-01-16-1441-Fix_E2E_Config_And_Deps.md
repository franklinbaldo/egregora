---
title: "🏗️ Fix E2E Tests: Config, Helpers & Dependencies"
date: 2026-01-16T14:41
---

## Observation
CI failures for PR #2561 persisted despite initial fixes.
1.  **Missing `test_config.py`:** Initially, the file was completely missing, causing `ModuleNotFoundError`.
2.  **Missing Helpers:** After restoring the file, `ImportError`s occurred because `WriteCommandOptions`, `assert_command_success`, and `build_write_command_args` were missing from it.
3.  **Dependency Conflicts:** Running E2E tests locally revealed a `ValueError: schema names don't match input data columns` deep within `ibis` -> `pandas` conversion. Investigation showed a conflict between `pandas>=2.3.0` and `ibis-framework`.
4.  **Database Connection Issues:** Downgrading `ibis-framework` to `10.0.0` caused a `ValueError: Don't know how to connect to 'duckdb://...'` error, indicating a regression or incompatibility with `duckdb` connection strings in that version.

## Action
I took the following steps:
1.  **Rebuilt `tests/e2e/test_config.py`:** Restored all missing dataclasses (`DateConfig`, `TimezoneConfig`, `WriteCommandOptions`) and helper functions (`assert_command_success`, `build_write_command_args`).
2.  **Fixed Linting:** Used `field(default_factory=lambda: ...)` for `ZoneInfo` defaults to satisfy `RUF009`.
3.  **Resolved Dependency Hell:**
    -   Upgraded `ibis-framework` back to `11.0.0` (which supports the connection string format).
    -   Pinned `pandas` to `<2.3.0` (specifically `2.2.3`) to resolve the schema/column mismatch error during `ibis` execution.
4.  **Verified Tests:** While full E2E execution hits API/token limits locally (expected), the specific `ImportError`s and `ValueError`s blocking progress have been resolved.

## Reflection
This task highlighted the fragility of Python dependency management when transitive dependencies (like `pandas` pulled in by `ibis` or `duckdb`) release breaking changes. The `schema names don't match` error was subtle and required inspecting the `ibis`/`pandas` integration layer. Pinning `pandas<2.3.0` is a necessary workaround until `ibis` or `duckdb` adapt to the upstream changes. Additionally, the tight coupling of E2E tests to shared helpers in `test_config.py` means that file is critical infrastructure for the test suite.
