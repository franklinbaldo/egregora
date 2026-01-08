# Architecture Overview

Egregora Pure adopts a functional pipeline architecture that processes data streams using the Atom protocol as its core data model.

## Key Concepts

*   **Atom-Centric:** All data flows as `Entry` or `Document` objects (Atom Feed entries).
*   **Synchronous Engine:** The core pipeline is synchronous and deterministic.
*   **Three-Layer Architecture:**
    1.  **Core Domain:** Types and Interfaces (no I/O).
    2.  **Engine/Infra:** Implementation of interfaces (RAG, SQL, Agents).
    3.  **Orchestration:** Pipelines and Workers.
