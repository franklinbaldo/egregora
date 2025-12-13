# TODO (Current Version – Egregora)

These tasks focus on improving the current architecture without unnecessary breaking changes for existing users.

## High Priority

- [x] **Decouple Writer Agent from Output Format**
  - **Rationale:** The writer currently assumes MkDocs structure. It should output agnostic `Document` objects that a separate adapter handles.
  - **Modules:** `src/egregora/agents/writer.py`, `src/egregora/agents/writer_tools.py`
  - **Implementation:** Updated `src/egregora/agents/writer.py` to rely on tool names (`write_post_tool`, `write_profile_tool`) instead of checking file path strings (e.g., `"/posts/"`). Removed explicit path replacement (`../media/` -> `/media/`) in `_save_journal_to_file`. Added regression test `tests/unit/agents/test_writer_logic.py`.

- [x] **Standardize CLI Entry Points**
  - **Rationale:** `egregora.cli.main` handles `write` orchestration directly. This logic should be moved to `src/egregora/orchestration/pipelines/write.py` to match the intended layering.
  - **Modules:** `src/egregora/cli/main.py`, `src/egregora/orchestration/`

- [ ] **Unify RAG Interfaces**
  - **Rationale:** References exist to both `egregora.rag` and `egregora.agents.shared.rag`. Consolidate into a single, clean `src/egregora/rag` package with a defined `VectorStore` protocol.
  - **Modules:** `src/egregora/rag/`, `src/egregora/agents/shared/rag/`

## Medium Priority

- [ ] **Centralize Privacy Utilities**
  - **Rationale:** Privacy logic (anonymization, PII redaction) is scattered across adapters and agents. Move to `src/egregora/privacy/`.
  - **Modules:** `src/egregora/input_adapters/`, `src/egregora/agents/writer_helpers.py`

- [ ] **Isolate MkDocs Publishing**
  - **Rationale:** MkDocs-specific logic (YAML manipulation, theme overrides) should live strictly in `src/egregora/output_adapters/mkdocs/`, not leak into general site generation code.
  - **Modules:** `src/egregora/rendering/`, `src/egregora/output_adapters/mkdocs/`

- [ ] **Clean Up `writer` Module Sprawl**
  - **Rationale:** The `writer` agent is split across `writer.py`, `writer_setup.py`, `writer_tools.py`, `writer_helpers.py`. Reorganize into a cohesive `src/egregora/agents/writer/` package.
  - **Modules:** `src/egregora/agents/writer*.py`

## Low Priority / Opportunistic

- [ ] **Remove Legacy V2-V3 Bridge Code**
  - **Rationale:** If V3 code (`src/egregora_v3`) is present, ensure no "temporary" bridges in V2 code are creating hidden dependencies.
  - **Modules:** `src/egregora/`

- [ ] **Improve Test Isolation**
  - **Rationale:** Many tests rely on VCR cassettes or live API calls. Introduce more `TestModel`-based tests for agents to reduce flake and cost.
  - **Modules:** `tests/`
