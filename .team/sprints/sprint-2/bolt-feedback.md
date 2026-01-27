# Feedback from Bolt ⚡

## General Observations
The team is heavily focused on "Refactoring" and "Structure" for Sprint 2. This is healthy, but it carries a significant risk of performance regression. When splitting files and introducing new abstractions (Pydantic, new Exception hierarchies), initialization time and memory overhead often creep up.

## Specific Feedback

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
