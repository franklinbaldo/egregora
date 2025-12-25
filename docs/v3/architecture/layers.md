# Architectural Layers

Egregora V3 is structured into three distinct layers to ensure separation of concerns and testability.

## 1. Core Domain (`src/egregora_v3/core`)

Defines the fundamental types (`Entry`, `Document`, `Feed`) and protocols (`LLMModel`, `DocumentRepository`). This layer contains **no business logic** and **no I/O**. It is purely declarative.

## 2. Infrastructure & Engine (`src/egregora_v3/infra`, `src/egregora_v3/engine`)

Implements the protocols defined in the Core.

*   **Infra:** Adapters for external systems (DuckDB, LanceDB, FileSystem).
*   **Engine:** The core logic units (e.g., `VectorEngine` for RAG, `RankingEngine` for ELO).

## 3. Orchestration (`src/egregora/orchestration` - *transitional*)

Wiring it all together into executable pipelines. This layer manages state (`PipelineContext`) and executes the `write` and `read` flows.
