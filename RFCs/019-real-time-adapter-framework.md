# RFC: Real-Time Adapter Framework
**Status:** Actionable Proposal
**Date:** 2024-07-26
**Disruption Level:** Medium - Fast Path

## 1. The Vision
This RFC proposes the creation of a foundational framework for real-time data ingestion, directly enabling the "Egregora Symbiote" moonshot. Instead of relying solely on batch file uploads, Egregora will gain the ability to connect to live message streams. This immediately unlocks the potential for near-instantaneous processing and response, transforming the system from a passive archivist into a dynamic, interactive platform.

## 2. The Broken Assumption
> "We currently assume that all input adapters must be batch-oriented, reading from a static file. This forces us into a high-latency, retrospective-only model and is the single biggest technical blocker to creating a real-time, interactive Egregora."

## 3. The First Implementation Path (≤30 days)
- **Step 1: Define `RealTimeInputAdapter` Protocol.** Create a new protocol in `src/egregora/input_adapters/protocols.py` that defines a `connect()` or `listen()` method. This adapter would yield `Entry` objects as they arrive, rather than returning a complete list.
- **Step 2: Create a Proof-of-Concept Adapter.** Implement a simple "WebSocket" or "Webhook" adapter. This adapter would listen on a local port for incoming JSON payloads and convert them into `Entry` objects in real time.
- **Step 3: Update `PipelineRunner` to support new protocol.** Modify the main pipeline orchestration to accept a `RealTimeInputAdapter`. It will need to be able to iterate over the yielded `Entry` objects and process them individually or in micro-batches.
- **Step 4: Add a new CLI command.** Introduce a new command, `egregora listen <adapter_name>`, to activate the real-time mode.

## 4. The Value Proposition
This is the fastest and most direct way to de-risk the "Egregora Symbiote" vision. It tackles the primary architectural constraint (batch processing) head-on. By building this framework, we create the on-ramp for all future real-time features. It's the critical first step that shifts Egregora's entire operational paradigm without breaking the existing, stable batch-processing functionality.

## 5. Success Criteria
- A new `egregora listen` command is available in the CLI.
- The proof-of-concept adapter can successfully receive a message and process it through the pipeline, resulting in a new entry in the database.
- The system can remain in a listening state indefinitely without crashing.
