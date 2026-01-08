# RFC: Real-Time Adapter Framework
**Status:** Actionable Proposal
**Date:** 2024-07-29
**Disruption Level:** Low - Fast Path

## 1. The Vision
To evolve Egregora from a historical archivist into a real-time participant (like the "Egregora Scribe"), we must first teach it to listen in real-time. This RFC proposes the creation of a foundational **Real-Time Adapter Framework**. The initial goal is not to build a full-featured Slack or Discord bot, but to establish the internal plumbing and protocols required to process a continuous stream of `Entry` objects, breaking our dependency on batch-processing ZIP files.

This quick win ladders up directly to the Moonshot by building the essential runway for any future real-time agent.

## 2. The Broken Assumption
This proposal challenges the architectural assumption that **all input data is bounded and available at the start of a pipeline run.**

> "Our current `InputAdapter` protocol is designed for a single, finite `read()` operation. This prevents us from handling continuous, unbounded data streams. We are breaking this assumption to enable a new class of long-lived, streaming pipelines."

## 3. The First Implementation Path (≤30 days)
1.  **Define a `StreamingInputAdapter` Protocol:**
    - Create a new protocol in `src/egregora/input_adapters/base.py`.
    - Unlike the current `InputAdapter`, this will not have a `read()` method that returns a full `Table`. Instead, it will be an `AsyncIterator` that `yield`s individual `Entry` objects as they arrive.
    - `async def listen(self) -> AsyncIterator[Entry]: ...`

2.  **Create a "Tail" Adapter for Development:**
    - Implement a simple `TailInputAdapter` that conforms to the new protocol.
    - This adapter will monitor a local file (e.g., `dev/live_chat.log`).
    - When a new line is appended to the file (simulating a new chat message), it will parse it into an `Entry` and `yield` it.
    - This provides a simple, dependency-free way to test real-time processing logic.

3.  **Update the PipelineRunner:**
    - Modify the `PipelineRunner` to accept a `StreamingInputAdapter`.
    - Instead of calling `read()`, it will `await` the stream from the adapter's `listen()` method.
    - For this initial implementation, the runner can simply process each `Entry` individually as it arrives, logging it to the console. Full agent processing is out of scope for this RFC.

## 4. The Value Proposition
This is the fastest and most direct way to de-risk the real-time vision.

*   **Unlocks Future Development:** All future real-time features (Zeitgeist, Scribe, etc.) depend on this foundational stream-processing capability.
*   **Architectural Evolution:** It forces us to evolve the core pipeline from a batch-oriented script to a persistent service, which is a necessary step for the project's growth.
*   **Isolates Complexity:** By starting with a simple file-tailing adapter, we can develop the core real-time logic without getting bogged down in the complexities of specific chat platform APIs.

## 5. Success Criteria
- [x] A `StreamingInputAdapter` protocol is defined and merged.
- [x] The `TailInputAdapter` is implemented and can successfully yield `Entry` objects from a watched file.
- [x] The `PipelineRunner` can consume the stream from the `TailInputAdapter` and process at least one entry.
