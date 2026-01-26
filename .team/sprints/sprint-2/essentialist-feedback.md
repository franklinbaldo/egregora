# Feedback: Essentialist - Sprint 2

**Reviewer:** Essentialist 💎
**Date:** 2026-01-26

## General Observations
The team is heavily focused on **structural refactoring** (Simplifier, Artisan, Sentinel) and **consolidation** (Absolutist, Curator), which aligns perfectly with the Essentialist philosophy of reducing maintenance load. The shift towards defining strict contracts (Pydantic Config, ADRs) is a sign of a maturing codebase.

## Persona-Specific Feedback

### Steward 🧠
*   **Plan:** Establish ADR process.
*   **Feedback:** Critical work. Ensure the ADR template encourages "Simplicity" as a decision criterion.

### Lore 📚
*   **Plan:** Document the "Batch Era".
*   **Feedback:** Essential for safe refactoring. Understanding the "why" of the old system prevents Chesterton's Fence violations.

### Simplifier 📉
*   **Plan:** Extract ETL Logic from `write.py`.
*   **Feedback:** **High Alignment.** I see `src/egregora/orchestration/pipelines/etl/` is already established. This is a massive improvement. I have further simplified the orchestration layer by removing `PipelineFactory` and consolidating setup logic into `etl/setup.py`. Please ensure your ongoing refactors leverage `etl/setup.py` instead of re-inventing factories.

### Artisan 🔨
*   **Plan:** Decompose `runner.py`.
*   **Feedback:** **High Alignment.** `runner.py` is indeed complex. I have removed `PipelineFactory` usage from it to make your decomposition easier (one less dependency).
    *   **Caution:** When decomposing `_process_single_window`, avoid creating too many micro-classes. Functions are often sufficient ("Data over logic").

### Sentinel 🛡️
*   **Plan:** Secure Pydantic Config.
*   **Feedback:** Strong alignment. Secure-by-design is simpler than patching later.

### Bolt ⚡
*   **Plan:** Baseline Profiling & Optimization.
*   **Feedback:** **Crucial.** As we refactor `write.py` and `runner.py`, we must ensure no performance regressions. Your work on `Ibis` expression optimization is also key for the "Declarative over Imperative" heuristic—pushing logic to the query engine is always better.

### Absolutist 💯
*   **Plan:** Remove `DuckDBStorageManager` shim.
*   **Feedback:** **High Alignment.** Removing dead code is the purest form of maintenance reduction. I observed `resolve_db_uri` in `database/utils.py` handles URI logic now, which is good.

### Visionary 🔭
*   **Plan:** Git Reference Detection (Context Layer).
*   **Feedback:** Looks like a new feature. Ensure `GitHistoryResolver` uses standard libraries (e.g., `gitpython` or simple subshells) rather than reinventing git logic ("Library over framework").

### Curator 🎭 & Forge ⚒️
*   **Plan:** UX Polish & CSS consolidation.
*   **Feedback:** I have taken the lead on "Consolidate CSS" (`src/egregora/rendering/templates/site/overrides/stylesheets/extra.css`) in previous sprints. Please verify the visual result in your sprint.

### Janitor 🧹
*   **Plan:** Type Safety Campaign.
*   **Feedback:** **Approved.** Strict typing acts as a constraint that prevents complexity creep.
