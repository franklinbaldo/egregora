---
title: "💣 Refactored Repository and Runner Exceptions"
date: 2026-01-16
author: "Sapper"
emoji: "💣"
type: journal
---

## 💣 2026-01-16 - Summary

**Observation:**
1.  `src/egregora/database/repository.py` was accessing a non-existent `doc.doc_type` attribute (the correct one is `doc.type`). This was likely causing `AttributeError` at runtime, although no explicit task reported it, my tests uncovered it immediately.
2.  `ContentRepository.save` method was not wrapping low-level database errors (from Ibis/DuckDB), allowing them to bubble up as raw exceptions or `Exception`.
3.  `src/egregora/orchestration/runner.py` was using broad `except Exception` blocks to catch failures, swallowing errors without specific context, particularly in `_fetch_processed_intervals`.

**Action:**
1.  **Refactor `ContentRepository.save`**:
    *   Fixed the attribute access bug: `doc.doc_type` -> `doc.type`.
    *   Wrapped the insertion logic in a `try...except` block that catches `Exception` and re-raises it as a context-rich `DatabaseOperationError`, preserving the stack trace.
    *   Verified this with a new TDD test file `tests/unit/database/test_repository_exceptions.py`.

2.  **Refactor `PipelineRunner._fetch_processed_intervals`**:
    *   Updated the exception handling to specifically catch `DatabaseOperationError` and log it with a distinct message, separate from unexpected `Exception`. This aligns with the "Trigger, Don't Confirm" philosophy by being explicit about what failure mode is being handled.
    *   Verified with `tests/unit/orchestration/test_runner_exceptions.py`.

**Reflection:**
The discovery of the `doc_type` bug was a surprise. It suggests that this code path might not have been fully covered by existing tests or that `Document` definition changed recently. By fixing it and wrapping the exceptions, we've made the persistence layer significantly more robust. The runner now handles database errors explicitly. There are still many `except Exception` blocks in `runner.py` (e.g., for individual item persistence), but these are arguably "graceful degradation" points. Future work could refine these further by introducing `PersistenceError` or similar, but for now, the critical `DatabaseOperationError` bridge is established.
