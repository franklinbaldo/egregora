# Plan: Bolt - Sprint 3

**Persona:** Bolt ⚡
**Sprint:** 3
**Created:** 2026-01-26
**Priority:** High

## Objectives
My mission is to enable the "Real-Time Adapter Framework" (Visionary's Moonshot) by optimizing for latency and concurrency, and to finalize the performance hardening of the Context Layer.

- [ ] **Async Core:** Refactor critical blocking I/O paths in the ingestion layer to be fully asynchronous (preparing for real-time streams).
- [ ] **Latency Budget:** Establish and enforce a "Latency Budget" for message processing (e.g., <50ms per message from ingestion to DB).
- [ ] **Stream Processing:** Prototype a stream-based processing model (using `async generators` or `trio`) to replace the batch-windowing logic for the real-time adapter.
- [ ] **Git History Optimization (Finalize):** Ensure the Git history resolution scale linearly with repo size, possibly implementing an incremental updater.
- [ ] **Load Testing:** Conduct load testing on the new architecture to identify breaking points.

## Dependencies
- **Visionary:** I need the "Real-Time Adapter Framework" RFC and initial prototype.
- **Sentinel:** Security checks must not introduce significant latency in the real-time path.

## Context
Sprint 3 is the "Pivot". We move from "Batch" to "Stream". This requires a fundamental shift in how we handle I/O and concurrency. My role is to ensure the python `asyncio` loop is not blocked and that we can handle high-throughput message streams.

## Expected Deliverables
1.  **Async Ingestion Layer:** Refactored input adapters.
2.  **Latency Monitor:** A tool or log wrapper to measure per-message processing time.
3.  **Load Test Report:** Analysis of system performance under load.

## Risks and Mitigations
| Risk | Probability | Impact | Mitigation |
|-------|---------------|---------|-----------|
| Python GIL limitations | Medium | High | Use multi-processing for CPU-bound tasks (if any), keep the main loop I/O bound. |
| DB Write Locking | Medium | High | Optimizing DuckDB write patterns or moving to a wal-enabled mode if not already. |
