# Egregora V3 Development Plan

## Project Goal
Refactor Egregora into a clean, synchronous, modular architecture (`src/egregora_v3`) following a Test-Driven Development (TDD) approach. The goal is to eliminate technical debt, unify data structures, and simplify the cognitive engine.

## Core Principles
1.  **Synchronous-First:** The core pipeline and internal interfaces must be synchronous (`def`). Concurrency is handled explicitly via `ThreadPoolExecutor` for I/O bound tasks, never `async`/`await` in the core logic.
2.  **Document Unification:** All content types (`Post`, `Profile`, `Journal`, `Enrichment`, `Media`) are specialized instances of a single `Document` primitive.
3.  **Strict Layering:** Dependencies flow inwards only: `Pipeline` -> `Engine` -> `Infra` -> `Core`. The Core layer has zero dependencies on outer layers.
4.  **LLM Abstraction:** The cognitive engine uses `pydantic-ai` Agents wrapped in a synchronous `LLMModel` interface to decouple the pipeline from specific LLM implementations.

## Architecture Layers

| Layer | Module (`src/egregora_v3/`) | Responsibility | Key Components |
| :--- | :--- | :--- | :--- |
| **L4: Orchestration** | `pipeline/` | Manages the workflow flow (Ingest, Window, Process, Publish). CLI entry point. | `PipelineRunner`, `WindowingEngine` |
| **L3: Cognitive Engine** | `engine/` | The "brains." Handles LLM interactions, tools, and prompts. Logic is divorced from I/O. | `WriterAgent`, `EnricherAgent`, `PydanticAgentWrapper` |
| **L2: Data Infrastructure**| `infra/` | Implementations of external resources: databases, vector stores, file I/O, adapters. | `DuckDBRepository`, `LanceDBVectorStore`, `MkDocsAdapter` |
| **L1: Core Domain** | `core/` | Defines the system's "grammar": data structures, configuration, and ports (Protocols). **No business logic or I/O.** | `types`, `config`, `ports` |

---

## Implementation Phases (TDD Execution)

### Phase 1: Core Foundation & Interfaces (Complete)
*   **1.1 Types:** Define `Document`, `FeedItem` (replaces Message), `DocumentType`. Implement content-addressed ID generation.
*   **1.2 Config:** Implement `EgregoraConfig` using Pydantic V2 with strict path resolution.
*   **1.3 Ports:** Define Protocols (`InputAdapter`, `DocumentRepository`, `VectorStore`, `LLMModel`, `UrlConvention`, `OutputSink`, `Agent`).

### Phase 2: Data Infrastructure
*   **2.1 Adapter:** Implement `WhatsAppAdapter` to parse export files into `FeedItem` streams.
*   **2.2 Repository:** Implement `DuckDBRepository` using Ibis for synchronous CRUD operations on `Document` and `FeedItem`.
*   **2.3 Vector Store:** Implement `LanceDBVectorStore` for RAG indexing and search.
*   **2.4 Output:** Implement `MkDocsAdapter` (OutputSink) and `StandardUrlConvention` for persisting documents to disk.

### Phase 3: Cognitive Engine
*   **3.1 LLM Client:** Implement `PydanticAgentWrapper` implementing `LLMModel`. Handles sync execution of `pydantic-ai` agents.
*   **3.2 Tools:** Implement `WriteDocumentTool`, `SearchRagTool`, etc., injecting L2 infrastructure components.
*   **3.3 Agents:** Implement `Agent` protocol.
    *   `EnricherAgent`: Enriches items/media.
    *   `WriterAgent`: Generates posts from item windows.

### Phase 4: Pipeline Orchestration
*   **4.1 Windowing:** Implement `WindowingEngine` to split item streams into overlapping windows based on time or count.
*   **4.2 Steps:** Implement functional pipeline steps (`anonymize`, `extract_media`).
*   **4.3 Runner:** Implement `PipelineRunner` to coordinate the full flow: Ingest -> Window -> Enrich -> Write -> Persist.
*   **4.4 CLI:** Implement `egregora` CLI using `typer`.

## Testing Strategy
*   **Unit Tests:** Strict isolation for Agents and Core logic.
*   **Integration Tests:** Verify Infrastructure implementations against real (or dockerized) databases.
*   **E2E Tests:** Run the full pipeline with a mocked LLM to verify data flow and file generation.
