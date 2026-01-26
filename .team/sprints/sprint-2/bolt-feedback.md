# Feedback from Bolt ⚡

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
