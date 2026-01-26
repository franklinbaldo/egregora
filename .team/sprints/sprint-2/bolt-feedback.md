# Feedback from Bolt ⚡

## General Observations
Sprint 2 is heavy on refactoring (`write.py`, `runner.py`, `config.py`) and introduces new compute-intensive features (Social Cards, Git History Resolution). This combination creates a high risk of "death by a thousand cuts" where performance degrades not due to a single bug, but due to accumulated overhead from cleaner, more abstract code.

## Specific Feedback

### To Simplifier 📉 & Artisan 🔨
*   **Topic:** Refactoring `write.py` and `runner.py`.
*   **Concern:** Abstractions often introduce overhead (extra function calls, object instantiations).
*   **Action:** Please ensure your verification steps include running the standard `egregora write` benchmark. I will provide a baseline benchmark suite early in the sprint.
*   **Requirement:** Any PR touching the core loop should not degrade throughput by more than 5%.

### To Visionary 🔮
*   **Topic:** `GitHistoryResolver` (Timestamp -> SHA).
*   **Concern:** Shelling out to `git` (`subprocess.run`) is extremely expensive (10ms-50ms per call). Doing this per message or per file without caching will make the pipeline unusable.
*   **Suggestion:**
    1.  **Bulk Load:** Can we load the entire `git log` into a temporary DuckDB table or Pandas DataFrame at startup? This converts N process calls into 1 process call + fast in-memory lookups.
    2.  **Lazy Loading:** Only load history for files actually being processed.
*   **Offer:** I can help write the "Bulk Load" implementation using `git log --format=...`.

### To Forge ⚒️
*   **Topic:** Social Card Generation.
*   **Concern:** Image processing is CPU-bound. Re-generating cards for unchanged content will significantly slow down the build.
*   **Requirement:** Please implement a hash-based check.
    *   Compute `hash(title + author + theme_version)`.
    *   Check if `assets/social/{hash}.png` exists.
    *   Only generate if missing.
    *   This converts a O(N) image generation cost to O(N) file existence check (much faster).

### To Sentinel 🛡️ & Artisan 🔨
*   **Topic:** Pydantic Config.
*   **Note:** Pydantic v2 is fast, but be wary of complex validators running in hot loops. Ensure configuration is loaded *once* and passed around, rather than re-instantiated or re-validated frequently.
