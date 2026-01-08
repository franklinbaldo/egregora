# Egregora V3: Strategic Vision (NEXT_VERSION_PLAN.md)

**"The Cathedral of Context"**

## 1. Executive Summary

Egregora V2 successfully proved the concept of converting chat logs into structured knowledge. However, the current architecture suffers from "God Classes" (Writer Agent), procedural coupling (Pipeline), and scattered concerns (Privacy, Media).

V3 introduces a **Functional Data Pipeline** architecture centered on the **Atom Protocol**. By treating all content as standardized `Entry` objects, we decouple ingestion, enrichment, and publication, allowing the system to scale to new sources and output formats without friction.

## 2. Core Architectural Pillars

### A. Atom-Centric Domain Model
*   **Single Source of Truth**: The `Entry` (and its subclass `Document`) is the universal unit of data.
*   **Standardization**: We adhere to RFC 4287 (Atom) for fields like `id`, `title`, `updated`, `authors`, `links`, and `content`.
*   **Extensions**: Internal metadata (vectors, internal flags) lives in `internal_metadata`, separated from the public Atom schema.

### B. Functional Pipeline (`Stream[Entry] -> Stream[Entry]`)
*   **Immutability**: Stages transform streams of entries rather than mutating global state.
*   **Explicit State**: State is passed explicitly via Context, never hidden in singletons.
*   **Sync Core**: The core pipeline remains synchronous (blocking) for simplicity and reliability, using thread pools for parallel I/O.

### C. The "Content Library" Facade
*   **Abstraction**: A unified interface (`ContentLibrary`) manages all persistence operations.
*   **Polymorphism**: The library handles Posts, Media, and Profiles uniformly.
*   **Storage Agnostic**: Whether data lives in Markdown files, Parquet, or a Database is an implementation detail hidden from the Agents.

### D. Strict Privacy Boundary
*   **Ingestion = Anonymization**: PII (Personally Identifiable Information) must be stripped or hashed *before* an `Entry` leaves the Ingestion Adapter.
*   **Zero-Trust Internal**: Internal components (RAG, Writer) operate on already-anonymized data. They do not need (and should not have) access to PII keys.

## 3. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Ingestion["Ingestion Layer (The Gatekeeper)"]
        WhatsApp[WhatsApp Adapter]
        Signal[Signal Adapter]
        Self[Self/Journal Adapter]
    end

    subgraph Core["Core Domain (Types & Protocols)"]
        Entry[Atom Entry]
        Feed[Atom Feed]
        Context[Pipeline Context]
    end

    subgraph Engine["The Engine (Functional Pipeline)"]
        Window[Windowing Strategy]
        Enrich[Enrichment Agents]
        Write[Writer Agent (Orchestrator)]
        Taxonomy[Taxonomy Agent]
    end

    subgraph Storage["Storage & Infrastructure"]
        Lib[Content Library Facade]
        DuckDB[(DuckDB / Ibis)]
        LanceDB[(LanceDB Vectors)]
        FS[Filesystem]
    end

    subgraph Output["Output Layer"]
        MkDocs[MkDocs Site Gen]
        RSS[RSS Feed Gen]
        Parquet[Parquet Archive]
    end

    WhatsApp -->|Raw Msg| Ingestion
    Ingestion -->|Anonymized Entry| Window
    Window -->|Batched Entries| Enrich
    Enrich -->|Enriched Entries| Write
    Write -->|Documents| Lib

    Lib --> DuckDB
    Lib --> FS

    Lib -->|Publish| Output
```

## 4. Migration Strategy (The Strangler Fig)

We will migrate from V2 to V3 incrementally, without a complete rewrite.

1.  **Phase 1: Structure & Boundaries (Current Focus)**
    *   Refactor `Writer` agent into a cohesive package.
    *   Extract `PipelineRunner` to isolate orchestration logic.
    *   Centralize PII stripping in adapters.

2.  **Phase 2: The Content Library**
    *   Introduce `ContentLibrary` alongside the existing file access code.
    *   Gradually switch consumers (Agents, RAG) to use `ContentLibrary`.
    *   Deprecate direct filesystem access in business logic.

3.  **Phase 3: Atom Standardization**
    *   Update `ibis` schemas to align strictly with the `Entry` model.
    *   Migrate legacy data to the new schema.

4.  **Phase 4: Functional Purity**
    *   Refactor the `PipelineRunner` to be fully stream-based.
    *   Remove remaining side-effects from transformation steps.
