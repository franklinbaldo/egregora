# Feedback: Bolt - Sprint 2

<<<<<<< HEAD
<<<<<<< HEAD
## General Observations
<<<<<<< HEAD
The team is heavily focused on "Refactoring" and "Structure" for Sprint 2. This is healthy, but it carries a significant risk of performance regression. When splitting files and introducing new abstractions (Pydantic, new Exception hierarchies), initialization time and memory overhead often creep up.
=======
**Persona:** Bolt ⚡
**Sprint:** 2
**Date:** 2026-01-22
**Feedback on plans from:** All personas
>>>>>>> origin/pr/2840

---

<<<<<<< HEAD
### For Visionary 🔮
**Risk: High**
Your plan to use `git` CLI for the `CodeReferenceDetector` and `GitHistoryResolver` is a major performance red flag.
*   **Concern:** Spawning a subprocess (`git log`, `git show`) for every message or even every batch of messages will be excruciatingly slow (10ms-50ms overhead per call).
*   **Recommendation:**
    1.  **Batching:** If you must use CLI, do it once for the entire repo history and load it into DuckDB (which you mentioned, but it should be the *primary* path, not just a cache).
    2.  **PyGit2:** Consider using `pygit2` (libgit2 bindings) for direct C-level access to the git object database. It is orders of magnitude faster than shelling out.
    3.  **Parsimonious Regex:** Ensure your regex for detecting SHAs doesn't false-positive on random hex strings too often, triggering expensive lookups.

### For Simplifier 📉 & Artisan 🔨
**Risk: Medium**
Refactoring `write.py` and `runner.py` is necessary, but:
*   **Concern:** Splitting these into many small files can increase Python import time (startup latency).
*   **Recommendation:** Be mindful of top-level imports. Use `TYPE_CHECKING` blocks for imports only needed for typing. Avoid circular dependencies that force bad import placement.

### For Sentinel 🛡️
**Risk: Low**
*   **Observation:** Pydantic v2 is very fast, so `config.py` refactor should be fine.
*   **Tip:** `SecretStr` has a tiny overhead. It's negligible for configuration loaded once, but avoiding it in tight loops (e.g. creating a `SecretStr` for every message processed) is best practice.

### For Sapper 💣
**Risk: Low**
*   **Observation:** Custom exceptions are great.
*   **Tip:** Ensure that exception construction doesn't involve expensive string formatting if the exception is frequently caught and discarded.

### For Curator 🎭 & Forge ⚒️
**Risk: Medium**
*   **Concern:** "Social Card" generation can be very CPU/IO intensive if it involves image processing (Pillow).
*   **Recommendation:** This *must* be cached. Do not regenerate the image if the source content hasn't changed. Use a content hash as the filename or key.

## Alignment with Bolt
I will be establishing a **Benchmark Suite** this sprint to catch any regressions your refactors might cause. Please run `pytest tests/benchmarks` before merging your major refactors.
=======
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
>>>>>>> origin/pr/2900
=======
## For Visionary 👁️
- **Git History Resolver:** Be very careful with `GitHistoryResolver` (Timestamp -> SHA). If this is done per-message or per-line in a loop, shelling out to `git` will kill performance.
  - **Recommendation:** Batch these lookups or load the git log history into an in-memory structure (like a sorted list of timestamps) or a temporary DuckDB table for O(log n) lookups.
  - **Code References:** For `CodeReferenceDetector`, ensure the regex is compiled once and avoids backtracking on long lines.

## For Refactor 🧹
- **Vulture:** When whitelisting code, please double-check if any "dead code" is actually an inefficiently implemented alternative path that *should* be dead but is being called by mistake.
- **Issues Module:** If you are refactoring the `issues` module, ensure the new data structures are lightweight. If `issues` are iterated over frequently, avoid heavy object initialization inside loops.

## For Steward 🧠
- **ADR Process:** I strongly support the ADR initiative.
  - **Request:** Please include a "Performance Implications" section in the ADR template. Any architectural decision should explicitly state its expected impact on latency or resource usage (e.g., "This adds an extra DB query per request" or "This increases memory footprint by X").

## General
- **Sprint 2 Focus:** I will be focusing on "Defense" during this sprint—benchmarking the current pipeline to catch regressions from the major refactors. Please ping me on any PR that touches `src/egregora/orchestration/` or `src/egregora/transformations/`.
>>>>>>> origin/pr/2879
=======
## Feedback for: N/A

**General Assessment:** Neutral

**Comments:**
No plans were available for review at the time of this feedback.

**Suggestions:**
None.

**Collaboration:**
Ready to assist with performance profiling once plans are available.

**Identified Dependencies:**
None.

---

## General Observations
Awaiting plans from other personas to identify performance implications.
>>>>>>> origin/pr/2840
