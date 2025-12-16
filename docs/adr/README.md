# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) documenting significant design decisions for Egregora.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](0001-media-path-convention.md) | Media Path Convention | Proposed |
| [ADR-002](0002-profile-path-convention.md) | Profile Path Convention | Proposed |

## Template

Use [template.md](template.md) for new ADRs.

## Migration Note (2025-12-16)

**V2 Shim vs V3 Source of Truth**

As part of the V3 refactor, core logic is moving to `src/egregora_v3`. The `src/egregora` package acts as a backward-compatibility shim.

*   **Source of Truth (V3):**
    *   `src/egregora_v3/core/config.py`: Core configuration (EgregoraConfig).
    *   `src/egregora_v3/core/utils.py`: Shared utilities (slugify).
    *   `src/egregora_v3/core/ingestion.py`: Document chunking logic.
    *   `src/egregora_v3/infra/vector/lancedb.py`: RAG Vector Store.

*   **Shim (V2):**
    *   `src/egregora/config/settings.py`: Re-exports V3 config.
    *   `src/egregora/rag/lancedb_backend.py`: Adapts V3 VectorStore to V2 interface.
    *   `src/egregora/utils/paths.py`: Wraps V3 slugify.

New development should import from `src/egregora_v3` where possible, but existing V2 code (Agents, Pipelines) can continue using `src/egregora` imports safely.
