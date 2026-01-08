# Architecture Review: Egregora

**Date:** 2024-05-22
**Status:** Architecture Audit & V3 Migration Assessment
**Reviewer:** Jules

---

## 1. High-Level Overview

**Purpose:** Egregora is a "Group Reflection Engine" that transforms raw chat logs (e.g., WhatsApp) into structured, privacy-preserving narratives (blog posts, biographies) using LLMs.

**Current State (V2):** The production codebase (`src/egregora`) is an **"Accidental Pipeline Monolith."** It evolved from a script-based approach into a complex set of orchestrators (`write.py`, `runner.py`) that tightly couple infrastructure (DuckDB/Ibis), configuration, and AI logic. While functional and feature-rich, it suffers from "God Object" anti-patterns in its orchestration layer and ambiguous data boundaries.

**Target State (V3):** The experimental V3 (`src/egregora_v3`) proposes a **"Strictly Layered, Atom-Centric"** architecture. It treats data as a stream of standardized `Atom Entries` and `Feeds`, processed by isolated Agents. This is the correct direction, offering decoupling and standard interoperability.

---

## 2. Architecture Map

### Current Architecture (`src/egregora`)
A "push-based" pipeline where the orchestrator drives everything.

```text
src/egregora/
├── orchestration/
│   ├── pipelines/write.py  <-- GOD SCRIPT (CLI, Config, DB setup, Loop)
│   ├── runner.py           <-- Duplicate Orchestrator (Window processing)
│   └── workers.py          <-- Background tasks (Banner, Profile)
├── agents/                 <-- Logic & Side Effects mixed
│   ├── writer.py           <-- Fetches data, calls LLM, writes files
│   └── tools/              <-- Direct DB/File I/O
├── database/               <-- Infrastructure
│   ├── duckdb_manager.py   <-- Tight coupling to DuckDB
│   └── repository.py       <-- Mixed domain/infra logic
└── input_adapters/         <-- Parsing + Privacy + Filtering
```

### Target Architecture (Refactoring Goal)
A "pull-based" or "graph-based" flow where data moves through transformations.

```text
app/
├── core/                   <-- Pure Domain (Atom Types, Protocols)
│   └── types.py            <-- Entry, Feed, Document
├── infra/                  <-- Adapters (Plugins)
│   ├── whatsapp.py         <-- Returns Iterator[Entry]
│   └── mkdocs.py           <-- Implements OutputSink protocol
├── engine/                 <-- Intelligent Processing
│   ├── agents/             <-- Pure Functions: Feed -> Document
│   └── graph/              <-- Pipeline definitions (DAGs)
└── cli/                    <-- Entry point (just wires the graph)
```

---

## 3. Strengths of Current System

*   **Rich Feature Set:** The V2 codebase handles complex real-world messiness (CLI args, timezone parsing, error recovery) that strictly "clean" architectures often miss initially.
*   **Strong Typing Foundation:** Use of Pydantic (`EgregoraConfig`, `Document`) and Ibis provides a good safety net, even if the connections are messy.
*   **Production Readiness:** Includes robustness features like rate limiting (`ratelimit`), retries (`tenacity`), and caching (`diskcache`) that are critical for LLM apps.
*   **Agent Tooling:** The separation of tools (`src/egregora/agents/tools/`) from the agent logic is a good first step towards modularity.

---

## 4. Key Problems & Smells

### 1. The Orchestration "God Knot"
*   **Smell:** `src/egregora/orchestration/pipelines/write.py` and `runner.py` are intertwined. `write.py` is 1000+ lines of CLI parsing, DB init, and looping. `runner.py` repeats validation and loop logic.
*   **Risk:** Extremely hard to test. You cannot test the "write loop" without mocking the entire universe (DB, FileSystem, Google API).
*   **Why it happens:** Lack of a clear `Pipeline` abstraction. The script *is* the pipeline.

### 2. Ambiguous Data Contracts
*   **Smell:** Data transforms mutably: `Ibis Table` -> `List[Dict]` -> `DTO` -> `Prompt String`.
*   **Example:** `runner.py` manually iterates over dicts to construct `Message` DTOs, filtering keys with `if k in valid_keys`. This "glue code" is fragile and hides the implicit schema.
*   **Risk:** Adding a new field (e.g., "reactions") requires updating the Ibis schema, the dictionary conversion logic, the DTO, and the prompt template manually.

### 3. Agent Side-Effects
*   **Smell:** Agents "pull" data and "push" results. The `Writer` agent calls `tools.write_post_impl` which directly writes to disk/DB.
*   **Risk:** Agents are hard to reuse. You can't use the `Writer` to "just generate text" for a preview window because it tries to save files to the `OutputSink`.
*   **Correction:** Agents should be **Functional**: `(Context, Input) -> Output`. Persistence is the job of the pipeline, not the agent.

### 4. V3 "Experiment" Isolation
*   **Smell:** `src/egregora_v3` exists as a completely separate tree.
*   **Risk:** It will rot. Codebases rarely survive "Big Bang" rewrites. V3 features will lag behind V2 fixes.
*   **Recommendation:** Stop developing V3 in isolation. Backport V3 concepts (Atom types, Protocols) into `src/egregora` incrementally.

---

## 5. Refactoring Roadmap

**Phase 1: solidify the Core (V3 Merge)**
*   **Goal:** Establish a shared domain model.
*   **Step 1:** Move `src/egregora_v3/core` to `src/egregora/core`.
*   **Step 2:** Refactor `InputAdapter`s to return `Iterator[Entry]` (Atom standard) instead of raw Ibis tables or dicts.
*   **Step 3:** Adopt `OutputSink` protocol strictly. Ensure `runner.py` never writes files directly, only via the sink.

**Phase 2: Purify Agents**
*   **Goal:** Make agents testable without mocks.
*   **Step 1:** Refactor `WriterAgent` to return a `Feed` or `List[Document]` object instead of calling `write_post_tool`.
*   **Step 2:** Move the "saving" logic out of the agent and into the `PipelineRunner`. The runner receives the documents and calls `sink.persist(doc)`.

**Phase 3: Decouple Orchestration**
*   **Goal:** Kill `write.py`.
*   **Step 1:** Create a `Pipeline` class that accepts `Source`, `Transform`, `Sink`.
*   **Step 2:** Move the CLI logic to just *configuring* this class.
*   **Step 3:** Delete `runner.py` and replacing it with the generic `Pipeline.run()`.

---

## 6. Guardrails & Conventions

1.  **Protocol-First:** Do not type-hint concrete classes (e.g., `MkDocsAdapter`). Type-hint Protocols (`OutputSink`).
2.  **No IO in Agents:** Agents must return data, not save it. The only exception is strictly temporary scratchpads.
3.  **One Way Data Flow:** Data flows `Adapter -> Entry -> Agent -> Document -> Sink`. No "loopbacks" where an output adapter reads from the DB.
4.  **Explicit Context:** Avoid "God Contexts" with 50 fields. Pass only what is needed (e.g., `AgentConfig`, not `GlobalConfig`).
