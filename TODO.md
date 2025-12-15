# Tactical Backlog for Egregora V3 Migration

This document outlines the concrete steps required to migrate the Egregora codebase from its current V2 structure to the V3 "Atom-Centric" architecture.

**Priorities:**
*   🔴 **High:** Critical architectural debt or blocking dependencies.
*   🟡 **Medium:** Feature refactors and cleanup.
*   🟢 **Low:** Optimization and polish.

---

## 🔴 Phase 1: Foundations (High Priority)

### 1. Unify Data Model (The "One Schema" Rule)
*   **Context:** Currently, we have `IR_MESSAGE_SCHEMA` (V2) in DuckDB and `Document` (V3) in Pydantic. This duality causes friction.
*   **Task:** Establish `Entry` as the base type and unify the database schema.
    *   [ ] **Create Core Types:** Create `src/egregora/core/types.py` defining `Entry` (Atom) and `Document` (System).
    *   [ ] **Refactor Document:** Update `src/egregora/data_primitives/document.py` to inherit from `Entry`.
    *   [ ] **Define Unified Schema:** Create `UNIFIED_SCHEMA` in `src/egregora/database/ir_schema.py` matching `Entry` fields.

### 2. Decouple Writer Agent ("God Class" Refactor)
*   **Context:** `src/egregora/agents/writer.py` is a monolithic file mixing orchestration, I/O, and logic.
*   **Task:** Decompose into the `src/egregora/agents/writer/` package.
    *   [ ] **Create Package:** Create `src/egregora/agents/writer/__init__.py`.
    *   [ ] **Extract Orchestrator:** Move `write_posts_for_window` to `src/egregora/agents/writer/orchestrator.py`.
    *   [ ] **Extract Context:** Move `WriterContext` and builders to `src/egregora/agents/writer/context.py`.
    *   [ ] **Extract Tools:** Move tool logic to `src/egregora/agents/writer/tools.py`.

---

## 🟡 Phase 2: Adaptation (Medium Priority)

### 3. Refactor WhatsApp Ingestion
*   **Context:** `WhatsAppAdapter` currently returns an Ibis table with V2 schema columns.
*   **Task:** Update adapter to produce `Entry` objects.
    *   [ ] **Update Parsing:** Modify `parse_source` in `src/egregora/input_adapters/whatsapp/parsing.py` to yield `Entry` instances.
    *   [ ] **Map Fields:** Ensure `author` maps to `Entry.authors` and `timestamp` to `Entry.updated`.

### 4. Isolate Privacy Logic
*   **Context:** Privacy logic is scattered in adapters and helper functions.
*   **Task:** Centralize privacy as a transformation stage.
    *   [ ] **Create Module:** Ensure `src/egregora/privacy` is the sole owner of PII logic.
    *   [ ] **Implement Filter:** Create a pipeable function `anonymize_stream(stream: Iterator[Entry]) -> Iterator[Entry]`.

---

## 🟢 Phase 3: Cleanup (Low Priority)

### 5. CLI Refactor
*   **Context:** CLI commands are functional but can be better organized.
*   **Task:** Group commands by domain.
    *   [ ] Use `typer` sub-apps for `data`, `agent`, `site`.

### 6. Remove Legacy Code
*   **Context:** V2 schemas and types will be obsolete.
*   **Task:** Delete unused code.
    *   [ ] Remove `IR_MESSAGE_SCHEMA` once `UNIFIED_SCHEMA` is fully adopted.
    *   [ ] Remove `WhatsAppExport` intermediate dataclass if no longer needed.
