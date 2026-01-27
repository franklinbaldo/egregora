# Architecture Review: Egregora

**Status:** Draft
**Date:** 2024-05-23
**Scope:** `src/egregora` (Current "V3" implementation)

## High-Level Overview

Egregora is a local-first, privacy-focused pipeline for transforming chat archives (WhatsApp) into structured static websites (MkDocs). Architecturally, it is a **Modular Monolith** that leverages a **Ports and Adapters** (Hexagonal) style for I/O.

The system is built on a modern data stack (**DuckDB**, **Ibis**, **LanceDB**) for local processing and uses **Pydantic-AI** for orchestrating LLM agents. Despite documentation references to a `src/egregora_v3` directory, the current `src/egregora` codebase *is* the V3 implementation, featuring the "Pure" architecture (Single Table Design, UUID/Slug Identity).

**Current Architecture Style:** Modular Monolith with Pipeline Orchestration.

### Top-Level Components
*   **Orchestration (`src/egregora/orchestration`):** The "nervous system." Coordinates data flow between adapters, agents, and persistence. The `write` command is the primary workflow, managed by `pipelines/write.py`.
*   **Agents (`src/egregora/agents`):** Domain logic. specialized workers (Writer, Profiler, Enricher) that use LLMs to transform data. Built on `pydantic-ai`.
*   **Data Primitives (`src/egregora/data_primitives`):** Core domain objects (`Document`, `Entry`) and Protocols (`OutputSink`, `SiteScaffolder`). This is the "Shared Kernel."
*   **Adapters (`src/egregora/input_adapters`, `output_sinks`):** The "Ports." Handle external systems (WhatsApp ZIPs, File System/MkDocs).
*   **Database (`src/egregora/database`):** Infrastructure layer. Manages DuckDB connection via Ibis for relational data and task storage.
*   **Config (`src/egregora/config`):** Centralized configuration management using `pydantic-settings`.

## Architecture Map

```text
src/egregora/
├── config/           # [Cross-Cutting] Centralized configuration (Pydantic Settings)
├── data_primitives/  # [Domain] Core types (Document) & Interfaces (Protocols)
├── input_adapters/   # [Port] Ingestion logic (WhatsApp, etc.)
├── output_sinks/  # [Port] Persistence logic (MkDocs, Filesystem)
├── database/         # [Infra] Persistence implementation (DuckDB, Ibis)
├── rag/              # [Infra] Vector search implementation (LanceDB)
├── agents/           # [Domain Services] Business logic & LLM interaction
│   ├── writer.py     # Main agent composition
│   └── tools/        # Pure function tool implementations
└── orchestration/    # [Application] Workflow coordination
    └── pipelines/    # High-level command flows (write.py)
```

## Strengths

*   **Strong Typing & Validation:** Pydantic is used pervasively (Config, Agent DTOs, Tools), ensuring data contract safety across boundaries.
*   **Configuration Centralization:** `src/egregora/config/settings.py` provides a robust, single source of truth for all system settings, supporting env overrides and validation.
*   **Tool Purity:** Agent tools (`src/egregora/agents/tools/`) are implemented as pure functions or simple wrappers, decoupled from the complex Agent execution loop. This makes them highly testable.
*   **Modern Data Stack:** The use of Ibis + DuckDB provides a unified, performant, and SQL-agnostic data access layer, future-proofing the storage backend.
*   **Protocol-Based Design:** The use of `Protocol` (e.g., `OutputSink`, `SiteScaffolder`) in `data_primitives` explicitly defines architectural boundaries, allowing for easy swapping of implementations.

## Key Problems & Smells

*   **Documentation vs. Reality Gap ("Ghost V3"):**
    *   **Problem:** Docs refer to a `src/egregora_v3` directory that does not exist.
    *   **Risk:** High confusion for new contributors. The current `src/egregora` *is* the V3 stack, but the folder structure implies it might be legacy V2.
    *   **Impact:** Onboarding friction and potential incorrect "fixes" trying to align code with stale docs.

*   **Pipeline Asymmetry:**
    *   **Problem:** The `write` command has a dedicated, robust pipeline definition in `orchestration/pipelines/write.py`. The `read` and `scaffold` commands lack equivalent pipeline structures, likely burying logic in CLI handlers or ad-hoc scripts.
    *   **Risk:** Inconsistent behavior, lack of observability/error handling for non-write commands.
    *   **Impact:** "Second-class citizen" status for features like Reader/Ranking.

*   **Infrastructure Leakage in Agents:**
    *   **Problem:** `src/egregora/agents/writer.py` contains significant logic for manual model rotation (`_execute_writer_with_error_handling`, retry loops, error parsing).
    *   **Risk:** Business logic (Writing) is coupled with Infrastructure concerns (LLM API resilience).
    *   **Impact:** Harder to test the "Writing" logic in isolation; changing LLM providers requires editing the Agent file.

*   **Orchestration "God Module":**
    *   **Problem:** `pipelines/write.py` is very large and handles everything from CLI argument parsing to ETL windowing to Agent execution.
    *   **Risk:** High complexity, difficult to unit test.
    *   **Impact:** Changes to the write flow are risky and slow.

## Refactoring Roadmap

### Phase 1: Stabilization & Cleanup (Immediate)
1.  **Documentation Sync:**
    *   Update `README.md` and `docs/` to reflect that `src/egregora` is the V3 codebase.
    *   Remove references to `egregora_v3`.
2.  **Codebase pruning:**
    *   Delete `src/egregora/orchestration/pipelines/write.py` legacy code blocks.

### Phase 2: Structural Standardization (Medium Term)
3.  **Standardize Pipelines:**
    *   Create `src/egregora/orchestration/pipelines/read.py` and `scaffold.py`.
    *   Move logic from CLI handlers into these pipelines to ensure uniform error handling and logging.
4.  **Decouple Orchestration:**
    *   Break `write.py` into smaller steps: `InputStage`, `ProcessingStage` (Agents), `OutputStage`.

### Phase 3: Infrastructure Extraction (Long Term)
5.  **Extract LLM Resilience:**
    *   Move the model rotation and error handling logic from `writer.py` into a dedicated `LLMClient` or `ModelGateway` in `src/egregora/llm/`.
    *   Agents should just call `model.generate()` and trust the infrastructure to handle retries/rotation.

## Updated Target Architecture (Conceptual)

```text
src/egregora/
├── domain/ (Future: Core logic, currently spread in agents/primitives)
├── infra/
│   ├── llm/          # NEW: Centralized Model Gateway (Rotation, Retry)
│   ├── database/     # Existing DuckDB/Ibis
│   └── fs/           # File system ops
├── pipelines/        # Standardized Workflows (Read, Write, Scaffold)
│   ├── stages/       # Reusable pipeline steps (ETL, Windowing)
│   └── write.py      # Composed pipeline, not monolithic script
└── ... (Adapters, Config stay same)
```

## Guardrails & Conventions

*   **Agents are Pure Consumers:** Agents must not implement low-level API resilience (retries, rotation). They consume an `LLMModel` interface that handles this.
*   **Pipelines Orchestrate, Don't Calculate:** Pipeline files should wire components together, not contain deep business logic or algorithms (e.g., windowing math should be in `transformations/`).
*   **Explicit IO Boundaries:** All disk/network I/O must go through `adapters` or `infra`. Domain objects (`Document`) should be pure data containers.
*   **Documentation First:** Any reference to "V3" implies the current `src/egregora` codebase.
