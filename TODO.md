# Tactical Backlog for Egregora V3 Migration

This document outlines the concrete steps required to migrate the Egregora codebase from its current V2 structure to the V3 "Atom-Centric" architecture.

**Priorities:**
*   🔴 **High:** Critical architectural debt or blocking dependencies.
*   🟡 **Medium:** Feature refactors and cleanup.
*   🟢 **Low:** Optimization and polish.

---

## 🔴 Phase 1: Foundations (High Priority)

### 1. Unify Data Model (The "One Schema" Rule)
*   **Context:** Currently, we have `IR_MESSAGE_SCHEMA` (V2) in DuckDB and `Entry`/`Document` (V3) in Pydantic. This duality causes friction.
*   **Task:** Migrate the DuckDB `documents` table to fully support the V3 `Entry` schema.
    *   [ ] Update `src/egregora/database/ir_schema.py` to match fields in `src/egregora_v3/core/types.py`.
    *   [ ] Add `doc_type` column (ENUM) to distinguish `message`, `post`, `profile`, `log`.
    *   [ ] Add `extensions` column (JSON) for Atom extensions.
    *   [ ] Create a migration script to alter existing tables.

### 2. Decouple Writer Agent ("God Class" Refactor)
*   **Context:** `src/egregora/agents/writer.py` mixes orchestration, I/O, RAG indexing, and LLM logic. It is difficult to test and maintain.
*   **Task:** Split `Writer` into distinct, single-responsibility components.
    *   [ ] Extract **Context Builder**: `(State) -> WriterContext`. Pure function.
    *   [ ] Extract **Decision Engine**: `(Context, Prompt) -> [Operations]`. Pure function returning intent.
    *   [ ] Extract **Effect Handler**: `([Operations]) -> IO`. Executes side effects (write files, index RAG).
    *   [ ] Remove direct calls to `_save_journal_to_file` and `index_documents` from the agent logic.

### 3. Restore Missing Utilities
*   **Context:** References to `egregora.utils.genai` exist in documentation/memory but the file is missing.
*   **Task:** Audit and consolidate GenAI utilities.
    *   [ ] Verify if `src/egregora/rag/embeddings.py` or `src/egregora/agents/banner/gemini_provider.py` covers the needs.
    *   [ ] If needed, create `src/egregora/utils/llm.py` as a central facade for model interactions (Embeddings, Completion).
    *   [x] **Centralize Privacy Utilities** - Completed: Privacy logic moved to `src/egregora/privacy/`.

---

## 🟡 Phase 2: Decoupling (Medium Priority)

### 4. Refactor WhatsApp Ingestion
*   **Context:** The `WhatsAppAdapter` emits raw rows/dicts that match the old IR schema.
*   **Task:** Update adapter to emit `Entry` objects.
    *   [ ] Modify `src/egregora/input_adapters/whatsapp` to parse messages into `Entry` (type=`message`).
    *   [ ] Ensure `author` is mapped to `Entry.authors`.
    *   [ ] Ensure `timestamp` is mapped to `Entry.updated`.

### 5. Centralize Privacy Utilities (From Original TODO)
*   **Context:** Privacy logic (anonymization, PII redaction) is scattered across adapters and agents.
*   **Task:** Consolidate into a dedicated module/agent.
    *   [ ] Create `src/egregora/privacy/` or `src/egregora/agents/privacy.py`.
    *   [ ] Move anonymization logic from `input_adapters` and `writer_helpers` to this new location.
    *   [ ] Ensure it operates on `Entry` objects (Feed -> Feed transformation).
    *   [ ] **Invariants:** Privacy must be an explicit pipeline stage or agent, not hidden in helpers.

### 6. Isolate MkDocs Publishing (From Original TODO)
*   **Context:** MkDocs-specific logic (YAML manipulation, theme overrides) leaks into general site generation code.
*   **Task:** Enforce strict separation.
    *   [ ] Move all MkDocs logic to `src/egregora/output_adapters/mkdocs/`.
    *   [ ] Ensure `SiteScaffolder` or `OutputSink` interfaces hide these details from the orchestration layer.

### 7. Clean Up `writer` Module Sprawl (From Original TODO)
*   **Context:** The `writer` agent is split across `writer.py`, `writer_setup.py`, `writer_tools.py`, `writer_helpers.py`, making navigation difficult.
*   **Task:** Reorganize into a cohesive package.
    *   [ ] Consolidate into `src/egregora/agents/writer/` package.
    *   [ ] Define a clear public API in `__init__.py`.

---

## 🟢 Phase 3: Migration & Polish (Low Priority)

### 8. CLI Cleanup
*   **Context:** CLI commands are functional but could use better structure.
*   **Task:** Refactor CLI to use `typer` best practices.
    *   [ ] Group commands by domain (`egregora data ...`, `egregora agent ...`).

### 9. Remove Legacy V2-V3 Bridge Code (From Original TODO)
*   **Context:** Temporary bridges might exist during migration.
*   **Task:** Audit and remove.
    *   [ ] Identify "shim" code converting `Entry` back to dicts.
    *   [ ] Remove once all consumers are V3-aware.

### 10. Improve Test Isolation (From Original TODO)
*   **Context:** Many tests rely on VCR cassettes or live API calls.
*   **Task:** Adopt `TestModel`.
    *   [ ] Introduce more `TestModel`-based tests for agents to reduce flake and cost.
    *   [ ] Reduce reliance on VCR for unit tests.

### 11. Plugin System
*   **Context:** Ad-hoc registry for adapters.
*   **Task:** Formalize the plugin interface.
    *   [ ] Use `entry_points` in `pyproject.toml` for adapter discovery.

---

## Completed Tasks (Retained History)

- [x] **Decouple Writer Agent from Output Format** (Original)
- [x] **Standardize CLI Entry Points** (Original)
- [x] **Unify RAG Interfaces** (Original)
