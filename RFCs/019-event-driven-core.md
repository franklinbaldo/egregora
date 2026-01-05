# RFC: The Event-Driven Core
**Status:** Actionable Proposal
**Date:** 2024-08-01
**Disruption Level:** Medium - Fast Path

## 1. The Vision
This RFC proposes a small but critical pivot to the V3 architecture. Instead of building the pipeline around batch processing of `Stream[Entry]`, we will refactor it to process a single `Entry` at a time. This change is invisible to the end-user for the current file-based workflow, but it is the **foundational enabler for the "Live Egregora" moonshot.** It transforms the core from a batch-oriented data processor into a real-time-ready event processor.

## 2. The Broken Assumption
This proposal challenges a subtle but powerful assumption in the `NEXT_VERSION_PLAN.md`:

> "We currently assume that **efficiency comes from batching.** This leads us to design a pipeline that requires a complete, finite collection of entries before it can run, making a real-time, single-event-driven system impossible."

By breaking this assumption, we can build a core that is simpler, more flexible, and ready for a future of real-time interaction without sacrificing the ability to process historical backlogs.

## 3. The First Implementation Path (≤30 days)
1.  **Refactor `PipelineRunner`:** Modify the central `run_cli_flow` (or equivalent) to iterate over entries from the input adapter and call a new `process_entry(entry)` method for each one. The batching logic (`Windowing`) becomes a stateful consumer of this event stream, emitting batches as needed, rather than a prerequisite.
2.  **Adapt Agents:** Ensure agents (Enrichment, Writer) can be initialized once and then receive single `Entry` objects for processing. Their internal logic may still perform micro-batching for API efficiency, but their public interface will be event-driven.
3.  **No User-Facing Changes:** The existing CLI `write` command will function identically. It will simply feed the entries from the file one by one into the new event-driven core.

## 4. The Value Proposition
- **De-risks the Moonshot:** This is the single most important step to make the "Live Egregora" technically feasible. It builds the real-time foundation *inside* the V3 architecture.
- **Simplifies Logic:** It disentangles the core processing logic from the batching/windowing strategy. The core pipeline becomes a simple `for entry in source: process(entry)` loop.
- **Future-Proofs the Architecture:** An event-driven core can handle batch backfills and real-time streams with the exact same logic, making the system far more adaptable.

## 5. Success Criteria
- The `egregora write` command continues to produce a bit-for-bit identical site from the same input file.
- The `PipelineRunner` (or equivalent) no longer has a main method that accepts a `list` or `stream` of entries, but instead processes them one by one.
- Code complexity (e.g., cyclomatic complexity) of the core pipeline orchestration logic is measurably reduced.
