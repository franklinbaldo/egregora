# Egregora V3: Strategic Vision (NEXT_VERSION_PLAN.md)

> **📋 Strategic Architecture Plan**
>
> This document outlines the roadmap for **Egregora V3**, the next-generation architecture designed for public/privacy-ready data processing.
>
> **Status:** Phase 1 (Core) Complete. Phases 2 (Infra) and 3 (Engine) In Progress.
> **Target:** Full V3 adoption by Q2 2026.

---

## 1. Executive Summary

Egregora V3 transforms the system from a chat-specific archive tool into a general-purpose **Atom Feed Processor**. By standardizing on the Atom Protocol (RFC 4287), we decouple ingestion, enrichment, and publication, enabling a robust, privacy-first pipeline.

### Key Shifts
| Feature | V2 (Legacy) | V3 (Target) |
| :--- | :--- | :--- |
| **Data Model** | Chat-specific DB Schema (`IR_MESSAGE_SCHEMA`) | Standard Atom `Entry` / `Feed` |
| **Privacy** | Leaky abstraction (passed to Agents) | Strict Boundary (Ingestion Only) |
| **Architecture** | "God Classes" & Procedural Scripts | Layered (Core, Infra, Engine, Pipeline) |
| **Identity** | Mixed (UUIDs vs Paths) | Semantic Identity (Slugs) + UUIDv5 |
| **Output** | Hardcoded MkDocs | Pluggable Sinks (MkDocs, RSS, JSON) |

---

## 2. Architecture Layers

The V3 architecture enforces a strict 4-layer design. Dependencies flow **inward only**.

```mermaid
flowchart TD
    subgraph Layer4[Layer 4: Pipeline]
        CLI[CLI Commands]
        Graph[Graph Orchestrator]
    end

    subgraph Layer3[Layer 3: Engine]
        Agents[LLM Agents (Writer, Enricher)]
        Tools[Agent Tools]
        Prompts[Jinja Templates]
    end

    subgraph Layer2[Layer 2: Infrastructure]
        Adapters[Input Adapters (WhatsApp, RSS)]
        Repos[Document Repository (DuckDB)]
        Vector[Vector Store (LanceDB)]
        Sinks[Output Sinks (MkDocs, Atom)]
    end

    subgraph Layer1[Layer 1: Core Domain]
        Entry[Atom Entry]
        Feed[Atom Feed]
        Config[EgregoraConfig]
        Ports[Interfaces / Protocols]
    end

    Layer4 --> Layer3
    Layer4 --> Layer2
    Layer3 --> Layer2
    Layer3 --> Layer1
    Layer2 --> Layer1
```

### Layer 1: Core Domain (`src/egregora_v3/core`)
*   **Status:** ✅ Mostly Complete.
*   **Responsibility:** Pure data models (`Entry`, `Document`), interfaces (`Ports`), and configuration. Zero external dependencies.
*   **Key Files:** `types.py` (Atom models), `ports.py` (Protocols).

### Layer 2: Infrastructure (`src/egregora_v3/infra`)
*   **Status:** 🔄 In Progress (Adapters & Repos exist).
*   **Responsibility:** I/O operations. Reading files, connecting to databases, writing output.
*   **Key Components:**
    *   `InputAdapter`: Converts raw source -> `Entry` stream.
    *   `DocumentRepository`: Persists `Document` objects.
    *   `OutputSink`: Publishes `Feed` objects to disk/network.

### Layer 3: Engine (`src/egregora_v3/engine`)
*   **Status:** 🔄 In Progress (Agents started).
*   **Responsibility:** Cognitive processing. LLM interactions, prompt rendering, tool execution.
*   **Key Components:**
    *   `WriterAgent`: Transforms Enriched Feed -> Post Feed.
    *   `EnricherAgent`: Transforms Raw Feed -> Enriched Feed.

### Layer 4: Pipeline (`src/egregora_v3/pipeline`)
*   **Status:** ⏳ Not Started (Planned).
*   **Responsibility:** Orchestration. Wiring layers together, managing execution flow (CLI, Graph).

---

## 3. Migration Strategy (The Strangler Fig)

We will not rewrite the system from scratch. We will incrementally replace V2 components with V3 implementations.

### Step 1: Data Model Unification (The Bridge)
*   **Goal:** Make V2 DB store V3 `Entry` data.
*   **Action:**
    1.  Update DuckDB schema to match `Entry` fields.
    2.  Update V2 `WhatsAppAdapter` to produce `Entry` objects (or map to them).
    3.  This allows V3 components to read legacy data.

### Step 2: Extract and Replace Infrastructure
*   **Goal:** Replace ad-hoc file I/O with V3 Repositories.
*   **Action:**
    1.  Implement `DuckDBDocumentRepository` in V3.
    2.  Refactor V2 `WriterAgent` to use this repository instead of direct SQL.
    3.  Implement `MkDocsOutputSink` in V3.
    4.  Refactor V2 pipeline to use this sink.

### Step 3: Engine Swap
*   **Goal:** Replace V2 Monolithic Writer with V3 Agents.
*   **Action:**
    1.  Finish `WriterAgent` in V3 (using `pydantic-ai`).
    2.  Update the CLI to invoke the V3 Agent instead of the V2 script.

### Step 4: Pipeline Orchestration
*   **Goal:** Finalize the transition.
*   **Action:**
    1.  Build the V4 Pipeline runner.
    2.  Switch the `egregora` CLI entry point to the new runner.
    3.  Delete `src/egregora` (V2 code).

---

## 4. Current Blockers & Risks

1.  **Documentation Drift:** The codebase is moving faster than the docs. We must keep this plan updated.
2.  **Schema Mismatch:** V2 DB schema is rigid. Migrating existing user databases to the new Atom-compatible schema requires careful migration scripts.
3.  **Dependency Leaks:** V2 code often imports from "sister" modules inappropriately. We need strict linting (e.g., `import-linter`) to enforce layer boundaries.

---

## 5. Vision: "Pipes + Reader + LLMs"

V3 envisions Egregora as a modern **Yahoo Pipes** or **Google Reader** powered by LLMs.
*   **Input:** Any Atom-compatible source (RSS, WhatsApp, API).
*   **Process:** A graph of AI Agents filtering, enriching, and summarizing.
*   **Output:** Any format (Blog, Newsletter, Database).

This aligns with the "Small Web" philosophy: own your data, process it locally, publish it openly.
