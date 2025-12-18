# Egregora V3: Tactical Backlog (TODO.md)

This backlog directs the engineering team on *what* to build next to stabilize the current architecture and prepare for the V3 migration.

**Priorities:**
*   🔴 **HIGH**: Blocking issues, critical technical debt, or architectural violations.
*   🟡 **MEDIUM**: Important refactors, feature enablers, or cleanup.
*   🟢 **LOW**: Nice-to-haves, minor cleanup, or optimizations.

---

## 🔴 High Priority (Blocking / Critical Debt)

- [ ] **[Data Model] Unify Data Model (The "One Schema" Rule)**
    - **Context:** Currently, we have `IR_MESSAGE_SCHEMA` (V2) in DuckDB and `Entry`/`Document` (V3) in Pydantic. This duality causes friction.
    - **Task:** Migrate the DuckDB `documents` table to fully support the V3 `Entry` schema.
    - **Action:**
        - Update `src/egregora/database/ir_schema.py` to match fields in `src/egregora_v3/core/types.py`.
        - Add `doc_type` column (ENUM) to distinguish `message`, `post`, `profile`, `log`.
        - Add `extensions` column (JSON) for Atom extensions.
        - Create a migration script to alter existing tables.

- [ ] **[Documentation] Resolve Documentation Drift**
    - **Context:** `docs/v3_development_plan.md` states "Phase 2 & 3 Not Started", but `src/egregora_v3/infra` and `src/egregora_v3/engine` exist and contain code.
    - **Task:** Audit and update the V3 plan to reflect reality.
    - **Action:**
        - Verify completeness of `src/egregora_v3/infra` adapters and repositories.
        - Verify completeness of `src/egregora_v3/engine` agents.
        - Update `NEXT_VERSION_PLAN.md` with accurate status.

- [ ] **[Privacy] Centralize PII Stripping in Ingestion**
    - **Context:** PII settings are passed deep into the Writer agent context (`WriterContext`), violating the "No PII leaves Ingestion" rule.
    - **Task:** Enforce PII stripping at the Adapter/Parser level.
    - **Action:**
        - Ensure `_parse_and_validate_source` returns a table where PII is *already* masked/hashed if privacy is enabled.
        - Remove PII logic from `WriterContext` and `WriterAgent`.

## 🟡 Medium Priority (Important Refactors)

- [ ] **[Infrastructure] Introduce `ContentLibrary` Abstraction**
    - **Context:** Code accesses `ctx.posts_dir` or `ctx.media_dir` directly.
    - **Task**: Create `ContentLibrary` in `src/egregora/knowledge/library.py` (or adopt `src/egregora_v3/core/catalog.py`?).
    - **Action**: Provide methods like `save_post(doc)`, `get_media(path)`.
    - **Goal**: Decouple business logic from the filesystem layout.

- [ ] **[Refactor] Modularize Writer Agent**
    - **Context:** `src/egregora/agents/writer.py` and its neighbors (`writer_helpers.py`, etc.) form a "God Module".
    - **Task**: Move these files into a package `src/egregora/agents/writer/`.
    - **Action**:
        - Create `src/egregora/agents/writer/__init__.py`.
        - Rename `writer.py` to `agent.py` (or keep as entry point).
        - Move helpers to submodules like `tools.py`, `context.py`, `deps.py`.
    - **Goal**: improve cohesion and discoverability.

- [ ] **[RAG] Decouple Indexing from Pipeline**
    - **Context**: `_index_new_content_in_rag` is called explicitly in the write loop.
    - **Task**: Use an event-based approach or a "Hook" system.
    - **Action**: `ContentLibrary.save_post()` could emit an event that the RAG system listens to.
    - **Goal**: Remove hard dependency on RAG from the core pipeline loop.

- [ ] **[Ingestion] Refactor WhatsApp Adapter to Produce Entry Objects**
    - **Context**: `WhatsAppAdapter` currently returns an Ibis table with V2 schema columns.
    - **Task**: Update adapter to produce `Entry` objects directly.
    - **Action**:
        - Modify `parse_source` in `src/egregora/input_adapters/whatsapp/parsing.py` to yield `Entry` instances.
        - Ensure `author` maps to `Entry.authors` and `timestamp` to `Entry.updated`.
    - **Goal**: Align ingestion with V3 data model.

- [ ] **[Testing] Add Architecture Tests**
    - **Context**: We must prevent dependency inversion violations (e.g., Domain importing Infra).
    - **Task**: Add a test suite that enforces layer boundaries.
    - **Action**: Use `pytest-archon` or simple import checks to fail if `src/egregora_v3/core` imports `src/egregora_v3/infra`.

## 🟢 Low Priority (Cleanup)

- [ ] **[CLI] Refactor Command Organization**
    - **Context**: CLI commands are functional but can be better organized by domain.
    - **Task**: Group commands using `typer` sub-apps.
    - **Action**: Create sub-apps for `data`, `agent`, `site` commands.

- [ ] **[Cleanup] Remove Legacy V2 Code**
    - **Context**: V2 schemas and types will be obsolete once V3 is adopted.
    - **Task**: Delete unused V2 code.
    - **Action**:
        - Remove `IR_MESSAGE_SCHEMA` once `UNIFIED_SCHEMA` is fully adopted.
        - Remove `WhatsAppExport` intermediate dataclass if no longer needed.

- [ ] **[Atom] Complete XML Serialization**
    - **Context**: `Feed.to_xml()` is implemented in V3 core but needs testing and validation against Atom validators.
    - **Task**: Verify RFC 4287 compliance.
    - **Action**: Add unit tests using `xmlschema` to validate generated feeds.
