# Tactical Backlog for Egregora V3 Migration

This document outlines the concrete steps required to migrate the Egregora codebase from its current V2 structure to the V3 "Atom-Centric" architecture.

**Priorities:**
*   🔴 **High:** Critical architectural debt or blocking dependencies.
*   🟡 **Medium:** Feature refactors and cleanup.
*   🟢 **Low:** Optimization and polish.

---

## 🔴 High Priority: The Core Foundation

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

---

## 🟡 Medium Priority: Input & Processing

### 4. Refactor WhatsApp Ingestion
*   **Context:** The `WhatsAppAdapter` emits raw rows/dicts that match the old IR schema.
*   **Task:** Update adapter to emit `Entry` objects.
    *   [ ] Modify `src/egregora/input_adapters/whatsapp` to parse messages into `Entry` (type=`message`).
    *   [ ] Ensure `author` is mapped to `Entry.authors`.
    *   [ ] Ensure `timestamp` is mapped to `Entry.updated`.

### 5. Consolidate Configuration
*   **Context:** `EgregoraConfig` is passed around, but some components still read env vars or have defaults hardcoded.
*   **Task:** Enforce strict config hygiene.
    *   [ ] Audit `src/egregora/agents` for `os.environ` usage.
    *   [ ] Move all defaults into `src/egregora/config/settings.py`.

### 6. Standardize Observability
*   **Context:** Logging is inconsistent. `UsageTracker` is manually passed.
*   **Task:** Implement a unified observer.
    *   [ ] Define a `Telemetry` protocol in `src/egregora_v3/core/ports.py`.
    *   [ ] Inject `Telemetry` into `PipelineContext`.

---

## 🟢 Low Priority: Polish

### 7. CLI Cleanup
*   **Context:** CLI commands are functional but could use better structure.
*   **Task:** Refactor CLI to use `typer` best practices.
    *   [ ] Group commands by domain (`egregora data ...`, `egregora agent ...`).

### 8. Plugin System
*   **Context:** Ad-hoc registry for adapters.
*   **Task:** Formalize the plugin interface.
    *   [ ] Use `entry_points` in `pyproject.toml` for adapter discovery.
