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

This roadmap is designed to be executed in small, incremental PRs. Each step brings the V2 codebase closer to V3 principles without stopping feature development.

### Phase 1: Core Consolidation & Type Safety (Weeks 1-2)
**Goal:** Establish a shared domain model by merging `src/egregora_v3/core` into the main application.

*   **Task 1.1: Merge Core Types**
    *   **Action:** Copy `src/egregora_v3/core/types.py` (Atom `Entry`, `Feed`, `Document`) to `src/egregora/core/types.py`.
    *   **Refactor:** Update `src/egregora/data_primitives/document.py` to inherit from or alias these new core types.
    *   **Verify:** Existing tests for `Document` still pass.

*   **Task 1.2: Standardize Protocols**
    *   **Action:** Copy `src/egregora_v3/core/ports.py` to `src/egregora/core/ports.py`.
    *   **Refactor:** Update `src/egregora/data_primitives/protocols.py` to use the new V3 protocols (`OutputSink`, `InputAdapter`).
    *   **Verify:** `mypy` passes on `src/egregora/output_adapters`.

*   **Task 1.3: Flatten Configuration**
    *   **Action:** Audit `EgregoraConfig` in `src/egregora/config/settings.py`. Move `EgregoraConfig` definition to `src/egregora/core/config.py`.
    *   **Goal:** Remove circular dependency risks by having config live in the Core layer.

### Phase 2: Agent Purification (Weeks 3-4)
**Goal:** Make agents purely functional (Input -> Output) and remove side effects (I/O).

*   **Task 2.1: Refactor `write_post_tool`**
    *   **Context:** Currently, `src/egregora/agents/tools/writer_tools.py` writes to disk via `ctx.output_sink.persist()`.
    *   **Action:** Change `write_post_tool` to return a `Document` object instead of writing it.
    *   **Update:** Update `WriterAgent` to collect these `Document` objects and return them as a list.

*   **Task 2.2: Lift Persistence to Runner**
    *   **Context:** `PipelineRunner.process_window()` currently ignores the return value of tools.
    *   **Action:** Update `PipelineRunner` to receive the `List[Document]` returned by the purified `WriterAgent`.
    *   **Action:** Iterate through the list and call `output_sink.persist(doc)` in the Runner, not the Agent.

*   **Task 2.3: Isolate `EnricherAgent`**
    *   **Action:** Apply the same pattern to `EnricherWorker`. It should return enriched `Entry` objects, not update the DB directly.

### Phase 3: Pipeline Abstraction (Weeks 5-6)
**Goal:** Decouple the "how" (orchestration) from the "what" (CLI/Config).

*   **Task 3.1: Define `Pipeline` Class**
    *   **Action:** Create `src/egregora/orchestration/pipeline.py`.
    *   **Interface:** `class Pipeline: def run(self, source: InputAdapter, sink: OutputSink): ...`
    *   **Refactor:** Move the loop logic from `runner.py` into this class.

*   **Task 3.2: Slim Down `write.py`**
    *   **Action:** Remove all DB initialization and logic from `src/egregora/orchestration/pipelines/write.py`.
    *   **Action:** `write.py` should only:
        1.  Parse CLI args.
        2.  Load Config.
        3.  Instantiate `Pipeline`.
        4.  Call `pipeline.run()`.

*   **Task 3.3: Functional Input Adapters**
    *   **Action:** Refactor `WhatsAppAdapter.parse()` to return a Python Generator `Iterator[Entry]` instead of an Ibis Table.
    *   **Benefit:** Allows streaming processing of infinite logs without memory issues.

### Quick Wins (Immediate)
*   **Fix 1:** Delete `src/egregora/agents/tools/definitions.py` if it duplicates `writer_tools.py`.
*   **Fix 2:** Rename `src/egregora/orchestration/pipelines/write.py` to `src/egregora/cli/commands/write.py` to reflect its true nature (CLI command, not pipeline logic).
*   **Fix 3:** Add a `Makefile` or `justfile` to standardize running tests and linting (currently relies on `uv` commands in docs).

---

## 6. Guardrails & Conventions

1.  **Protocol-First:** Do not type-hint concrete classes (e.g., `MkDocsAdapter`). Type-hint Protocols (`OutputSink`).
2.  **No IO in Agents:** Agents must return data, not save it. The only exception is strictly temporary scratchpads.
3.  **One Way Data Flow:** Data flows `Adapter -> Entry -> Agent -> Document -> Sink`. No "loopbacks" where an output adapter reads from the DB.
4.  **Explicit Context:** Avoid "God Contexts" with 50 fields. Pass only what is needed (e.g., `AgentConfig`, not `GlobalConfig`).
