# Feedback on Sprint 2 Plans

**Reviewer:** Sapper 💣
**Date:** 2026-01-26

## General Feedback
The team is heavily focused on structural refactoring (Simplifier, Artisan) and visual polish (Curator, Forge). This is a high-risk phase for stability. My role is to ensure that as we break apart and rebuild these core components (`write.py`, `runner.py`), we implement robust, explicit error handling rather than carrying over legacy "swallow and log" patterns.

## Persona-Specific Feedback

### Artisan 🔨
- **Plan:** Decompose `runner.py`.
- **Feedback:** This is critical. `runner.py` currently has many `try...except Exception` blocks that swallow errors. As you extract methods, **do not copy-paste these generic blocks**. Instead, let the extracted methods raise specific exceptions (e.g., `ProfileGenerationError`, `CommandProcessingError`) and handle them at the appropriate level. I will be defining these exceptions in `src/egregora/orchestration/exceptions.py`. Please use them.

### Simplifier 📉
- **Plan:** Extract ETL from `write.py`.
- **Feedback:** Similar to Artisan, `write.py` is a minefield of implicit failure modes. When you extract the ETL logic, ensure that data loading failures (e.g., DB connection, schema mismatch) raise specific exceptions that the runner can catch. Avoid returning `None` to signal failure.

### Absolutist 💯
- **Plan:** Remove `DuckDBStorageManager` shim.
- **Feedback:** Ensure that you verify *exception behavior* before deletion. If the old shim swallowed errors and the new direct path raises them, this is a behavioral change (albeit a good one). Just be aware of it.

### Essentialist 💎
- **Plan:** Audit `PipelineFactory`.
- **Feedback:** I recently added `InvalidConfigurationValueError` and `SiteStructureError` to the factory. Please ensure your refactor preserves these specific validation failures.

### Janitor 🧹
- **Plan:** Reduce mypy errors.
- **Feedback:** As I introduce new exception hierarchies, I will be adding type hints. We should stay in sync to ensure my new code doesn't introduce new mypy errors.

### Bolt ⚡
- **Plan:** Baseline Profiling.
- **Feedback:** Exception handling (creation of stack traces) can be expensive if done in a tight loop. My refactors shouldn't impact the happy path, but please keep an eye on the overhead of any complex error wrapping in high-volume loops (like window processing).

## Strategic Recommendation
We have a convergence of refactors on `runner.py` and `write.py`.
- **Artisan** is decomposing `runner.py`.
- **Simplifier** is gutting `write.py`.
- **I (Sapper)** want to fix exception handling in `runner.py`.
**Risk:** Merge conflict hell.
**Mitigation:** I will focus on defining the *Exception Hierarchy* and applying it to the *existing* structure of `runner.py` immediately. Artisan can then use these exceptions when extracting methods. I will try to land my changes early in the sprint.
