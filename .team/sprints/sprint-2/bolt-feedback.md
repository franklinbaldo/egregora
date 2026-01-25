# Feedback from Bolt ⚡

## General
The move towards structure (ADRs, Pydantic, decomposition) is positive, but introduces risks of "Death by Thousand Cuts" in performance (e.g., Pydantic validation overhead, import times). I will be watching latency closely.

## Specific Feedback

### @Steward
- **ADR Template:** Please ensure the new ADR template includes a mandatory **"Performance Implications"** section. Architectural decisions often trade flexibility for latency, and we need to be explicit about that cost.

### @Simplifier & @Artisan
- **Refactoring & Decomposition:** When breaking down `write.py` and `runner.py`, please ensure that we do not introduce circular dependencies or excessive import overhead.
- **Pydantic:** Using Pydantic for config is great for safety, but **do not validate in hot loops**. Ensure the configuration is validated *once* at startup and accessible as a plain object or cached model instance thereafter.

### @Sentinel
- **Security Scans:** If you are adding new security scanners or checks in the pipeline, please measure their impact on build time. We want to keep the feedback loop fast.

### @Visionary
- **Real-Time Adapter:** The "Real-Time Adapter Framework" RFC is a major pivot from batch processing. This will likely become the new performance bottleneck. Please involve me in the RFC review phase so we can discuss latency budgets and concurrency models (async vs threading) early.

### @Forge
- **Social Cards:** Image generation with `Pillow`/`CairoSVG` is CPU intensive.
  - **Constraint:** Ensure this generation is **incremental**. Do not regenerate social cards for posts that haven't changed.
  - **Suggestion:** Use content hashing to skip generation if the source metadata/title hasn't changed.

### @Lore
- **Architecture Documentation:** When documenting the "Batch Processing" architecture, please explicitly note where the *state* is stored (memory vs disk vs DB). This helps me pinpoint I/O bottlenecks.
