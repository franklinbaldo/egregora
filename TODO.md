# Egregora V3: Tactical Backlog (TODO.md)

This backlog directs the engineering team on *what* to build next to stabilize the current architecture and prepare for the V3 migration.

**Priorities:**
*   🔴 **HIGH**: Blocking issues, critical technical debt, or architectural violations.
*   🟡 **MEDIUM**: Important refactors, feature enablers, or cleanup.
*   🟢 **LOW**: Nice-to-haves, minor cleanup, or optimizations.

---

## 🔴 High Priority (Blocking / Critical Debt)

### 1. Unify Data Model (The "One Schema" Rule)
*   **Context:** Currently, we have `IR_MESSAGE_SCHEMA` (V2) in DuckDB and `Entry`/`Document` (V3) in Pydantic. This duality causes friction.
*   **Task:** Migrate the DuckDB `documents` table to fully support the V3 `Entry` schema.
    *   [x] Update `src/egregora/database/ir_schema.py` to match fields in `src/egregora_v3/core/types.py`.
    *   [ ] Add `doc_type` column (ENUM) to distinguish `message`, `post`, `profile`, `log`.
    *   [ ] Add `extensions` column (JSON) for Atom extensions.
    *   [ ] Create a migration script to alter existing tables.

- [ ] **[Refactor] Extract `write_pipeline.py` to `PipelineRunner`**
    - **Context**: `write_pipeline.py` is a procedural script that mixes high-level orchestration with low-level details.
    - **Task**: Create a `PipelineRunner` class in `src/egregora/orchestration/runner.py`.
    - **Action**: Move the `run()` loop and window processing logic into this class. Use Dependency Injection to pass `PipelineContext` and `OutputSink`.
    - **Goal**: Make the pipeline testable without running the full CLI command.

- [ ] **[Refactor] Modularize Writer Agent**
    - **Context**: `src/egregora/agents/writer.py` and its neighbors (`writer_helpers.py`, etc.) form a "God Module".
    - **Task**: Move these files into a package `src/egregora/agents/writer/`.
    - **Action**:
        - Create `src/egregora/agents/writer/__init__.py`.
        - Rename `writer.py` to `agent.py` (or keep as entry point).
        - Move helpers to submodules like `tools.py`, `context.py`, `deps.py`.
    - **Goal**: improve cohesion and discoverability.

- [ ] **[Privacy] Centralize PII Stripping in Ingestion**
    - **Context**: PII settings are passed deep into the Writer agent context, violating the "No PII leaves Ingestion" rule.
    - **Task**: Enforce PII stripping at the Adapter/Parser level.
    - **Action**: Ensure `_parse_and_validate_source` returns a table where PII is *already* masked/hashed if privacy is enabled. Remove PII logic from `WriterContext`.

## 🟡 Medium Priority (Important Refactors)

- [ ] **[Infrastructure] Introduce `ContentLibrary` Abstraction**
    - **Context**: Code accesses `ctx.posts_dir` or `ctx.media_dir` directly.
    - **Task**: Create `ContentLibrary` in `src/egregora/knowledge/library.py`.
    - **Action**: Provide methods like `save_post(doc)`, `get_media(path)`.
    - **Goal**: Decouple business logic from the filesystem layout.

- [ ] **[RAG] Decouple Indexing from Pipeline**
    - **Context**: `_index_new_content_in_rag` is called explicitly in the write loop.
    - **Task**: Use an event-based approach or a "Hook" system.
    - **Action**: `ContentLibrary.save_post()` could emit an event that the RAG system listens to.
    - **Goal**: Remove hard dependency on RAG from the core pipeline loop.

- [ ] **[Database] Dependency Injection for Storage**
    - **Context**: `DuckDBStorageManager` is instantiated inside `write_pipeline.py`.
    - **Task**: Pass storage managers via `PipelineContext` or a `ServiceContainer`.
    - **Action**: Update `PipelineContext` to hold the initialized storage strategies.

- [ ] **[Ingestion] Refactor WhatsApp Adapter to Produce Entry Objects**
    - **Context**: `WhatsAppAdapter` currently returns an Ibis table with V2 schema columns.
    - **Task**: Update adapter to produce `Entry` objects directly.
    - **Action**:
        - Modify `parse_source` in `src/egregora/input_adapters/whatsapp/parsing.py` to yield `Entry` instances.
        - Ensure `author` maps to `Entry.authors` and `timestamp` to `Entry.updated`.
    - **Goal**: Align ingestion with V3 data model.

- [ ] **[Privacy] Isolate Privacy Logic as Stream Transformation**
    - **Context**: Privacy logic is scattered across adapters and helpers.
    - **Task**: Centralize privacy as a functional transformation stage.
    - **Action**:
        - Ensure `src/egregora/privacy` is the sole owner of PII logic.
        - Create a pipeable function `anonymize_stream(stream: Iterator[Entry]) -> Iterator[Entry]`.
    - **Goal**: Make privacy a pure, composable transformation.

## 🟢 Low Priority (Cleanup)

- [ ] **[CLI] Refactor Command Organization**
    - **Context**: CLI commands are functional but can be better organized by domain.
    - **Task**: Group commands using `typer` sub-apps.
    - **Action**: Create sub-apps for `data`, `agent`, `site` commands.
    - **Goal**: Improve CLI discoverability and maintainability.

- [ ] **[Cleanup] Remove Legacy V2 Code**
    - **Context**: V2 schemas and types will be obsolete once V3 is adopted.
    - **Task**: Delete unused V2 code.
    - **Action**:
        - Remove `IR_MESSAGE_SCHEMA` once `UNIFIED_SCHEMA` is fully adopted.
        - Remove `WhatsAppExport` intermediate dataclass if no longer needed.
        - Audit and remove other V2-specific types and helpers.
    - **Goal**: Reduce technical debt and code complexity.

- [ ] **[Cleanup] Remove Legacy Pandas Compat**
    - **Context**: `pyproject.toml` contains `flake8-tidy-imports` bans for pandas, but some compat code might exist.
    - **Task**: grep for `pandas` and remove unused compatibility shims if Ibis is fully adopted.

- [ ] **[Testing] Add Architecture Tests**
    - **Task**: Add a test that fails if `agents` import `cli` or `orchestration`.
    - **Goal**: Prevent dependency inversion violations.
