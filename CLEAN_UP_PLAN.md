# Egregora Clean Up Plan

This document outlines a detailed and actionable plan to reduce complexity, eliminate duplication, and standardize infrastructure in the Egregora codebase, based on the Code Quality Report.

## 1) Configuration: Simplify and Consolidate

**Problem:** The config system is over-engineered with multiple layers (`settings.py`, `overrides.py`, `config_validation.py`) and unused validators.

**Actionable Steps:**

*   [ ] **Consolidate Settings:** Refactor `src/egregora/config/settings.py` to contain a single `Settings(BaseSettings)` class.
*   [ ] **Unify Load Order:** Implement a strict precedence: Environment Variables → Config File (`egregora.toml`) → CLI Overrides.
*   [ ] **Direct Injection:** Modify `src/egregora/orchestration/cli.py` to pass CLI arguments directly to the `Settings` constructor or a factory method, removing the need for a separate intermediate `overrides` builder.
*   [ ] **Delete Unused Code:**
    *   Remove `src/egregora/config/overrides.py`.
    *   Remove `src/egregora/config/config_validation.py` (move essential validators to `Settings`).
*   [ ] **Dependencies:**
    *   Ensure `pydantic-settings` is the primary driver.
    *   (Optional) Add `python-dotenv` if explicit `.env` file support is required beyond Pydantic's default.

## 2) Infrastructure: Modernize Rate Limiting & Routing

**Problem:** Custom `GlobalRateLimiter`, "len(text)//4" token estimation, and complex threading-based embedding routers are reinventing standard wheels and introducing race conditions.

**Actionable Steps:**

*   [ ] **Replace Rate Limiter:**
    *   Remove `src/egregora/utils/rate_limit.py`.
    *   Install/Use `aiolimiter` for async rate limiting.
    *   Standardize retry logic using `tenacity` (already a dependency) across all API clients.
*   [ ] **Fix Token Estimation:**
    *   Replace `len(text) // 4` heuristics with a real tokenizer (e.g., `tiktoken`) or utilize the provider's `count_tokens` API endpoint where available.
*   [ ] **Simplify Embedding Router:**
    *   **Invariant:** Enforce "Always Call Batch Endpoint". Even for a single item, use the batch API. This eliminates the branching logic between "single" and "batch" modes.
    *   **Remove Complexity:** Delete the custom thread-based queuing and "best-effort" batching logic.
    *   If a queue is absolutely necessary, use a standard `asyncio.Queue` with a single consumer task.

## 3) Caching: Remove Abstractions

**Problem:** `src/egregora/utils/cache.py` is an over-abstracted wrapper around `diskcache` with unnecessary complexity (e.g., XML-based hashing).

**Actionable Steps:**

*   [ ] **Direct Usage:** Refactor client code to use `diskcache.Cache` directly or via a very thin factory function.
*   [ ] **Simplify Keys:** Switch cache key generation to use canonical JSON serialization + SHA256.
    *   Drop the custom XML construction for hashing.
    *   (Optional) Add `orjson` for faster, deterministic JSON serialization.
*   [ ] **Flatten Tiers:** Remove the "Tiered Cache" logic (Memory -> Disk) unless metrics prove it provides a significant performance benefit over pure DiskCache (which is already fast).

## 4) Database: Drop Jinja2 for SQL

**Problem:** `SQLManager` (`src/egregora/database/sql.py`) uses Jinja2 templates for SQL generation, which is essentially a homegrown, risky query builder.

**Actionable Steps:**

*   [ ] **Migration:**
    *   For complex analytical queries: Rewrite using **Ibis** expressions (`ibis-framework[duckdb]`).
    *   For simple CRUD: Use standard parameterized SQL (e.g., `conn.execute("SELECT * FROM t WHERE id = ?", [id])`).
*   [ ] **Delete:** Remove `src/egregora/database/sql.py` and delete the `src/egregora/resources/sql/` directory once migration is complete.
*   [ ] **Dependencies:** Verify `ibis-framework` and `duckdb` are properly pinned.

## 5) Documentation: Unify Conventions

**Problem:** Inconsistent paths for media (`docs/media` vs `docs/posts/.../media`) and ADRs (`docs/adr` vs `docs/adrs`).

**Actionable Steps:**

*   [ ] **Standardize Media:**
    *   **Decision:** Adopt **`docs/media/`** as the single global root for assets to simplify path resolution.
    *   Update all strictures and documentation to reflect this.
*   [ ] **Standardize ADRs:**
    *   Ensure only **`docs/adr/`** exists. Rename/Move any content from `docs/adrs/` if it exists.
*   [ ] **Improve UX:**
    *   Replace custom JavaScript carousels with `mkdocs-glightbox` for image handling.
    *   Use `mkdocs-gen-files` if dynamic index generation is needed.

## 6) Cleanup: Dead Code Elimination

**Problem:** `vulture` reports numerous unused classes, variables, and methods.

**Actionable Steps:**

*   [ ] **Immediate Purge:**
    *   Delete unused enums and constants flagged by `vulture`.
    *   Remove unused commands in the CLI.
    *   Delete the `model_fallback.py` or similar complex retry mechanisms if replaced by `tenacity`.
*   [ ] **System Pruning:**
    *   Identify and remove unused subsystems (e.g., model key rotator, complex model cyclers) if they are not wired into the main pipeline.

---

**Execution Strategy:**
It is recommended to tackle these in the following order:
1.  **Dead Code & Config:** Quick wins, reduces noise.
2.  **Infrastructure (Rate Limit/Cache):** Reduces runtime complexity.
3.  **Database/SQL:** Improves safety and maintainability.
