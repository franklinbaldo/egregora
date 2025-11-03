# Pydantic-AI Migration Plan

This document tracks the ongoing work to refactor Egregora's Gemini integrations to use [Pydantic-AI](https://ai.pydantic.dev/). The goal is to replace the bespoke SDK dispatchers/batch clients with Agents that run on the Gemini REST API (or deterministic stubs in tests), while keeping the high-level pipeline (writer, editor, ranking, enrichment) unchanged from the user's perspective.

## Objectives

1. **Simplify transport** – Drop the `GeminiDispatcher`/`GeminiBatchClient` layer for the new backend and call the REST endpoints (or Pydantic-AI wrappers) directly.
2. **Uniform agent workflow** – Express writer, editor, ranking, and enrichment interactions as Pydantic-AI agents with explicit tools, context helpers, and structured outputs.
3. **Deterministic testing** – Replace VCR-style SDK fixtures with Pydantic-AI `FunctionModel`/`TestModel` stubs and message-log replay, so tests run without network calls.
4. **RAG via Pydantic helper** – Leverage `pydantic_ai.integrations.rag.rag_context` to build standard retrieval prompts instead of hand-crafted dispatcher queries.
5. **Recording & replay** – Continue writing transcripts to disk (via `ModelMessagesTypeAdapter`) and add CLI flags to toggle between live runs and replayed responses.

## Working Branches

- `chore/ban-relative-imports`: enforced absolute imports and removed `src/__init__.py`.
- `feature/vcr-full-pipeline-tests`: current active branch for the migration. Contains the writer Pydantic agent, test scaffold, and will host further changes.

## Phase-by-Phase Plan

### Phase 0 – Inventory (✅ complete)
- [x] Catalogue every place that imported `google.genai` and identify the response shapes/tools used.
- [x] Remove the transport shim (`gemini_transport.py`) from the tree to avoid confusion.
- [x] Build a reference test (`tests/test_writer_pydantic_agent.py`) to exercise the new path.

### Phase 1 – Writer Agent (⚙ in progress)
- [x] Implement `write_posts_with_pydantic_agent` (env toggled via `EGREGORA_LLM_BACKEND=pydantic`).
- [x] Provide deterministic tests using `TestModel` (added in `tests/test_writer_pydantic_agent.py`).
- [ ] Swap `_query_rag_for_context` with Pydantic’s `rag_context()` helper.
- [ ] Allow the agent to accept async streaming responses (align CLI writer tooling).

### Phase 2 – Editor Agent
- [ ] Recreate the editor workflow with an async Pydantic Agent mirroring the existing tools (edit_line, full_rewrite, finish, etc.).
- [ ] Add tests using a function-based stub that returns deterministic edits.
- [ ] Integrate the new agent behind `EGREGORA_LLM_BACKEND` switch.

### Phase 3 – Ranking & Enrichment
- [ ] Convert ranking judge (Elo comparisons) to a Pydantic Agent; provide deterministic stub results.
- [ ] Replace the enrichment batch paths (media/URL) with agents that call REST endpoints sequentially.
- [ ] Remove `GeminiBatchClient` usage where possible (keep for legacy path only if necessary).

### Phase 4 – RAG & Tooling
- [ ] Wrap our DuckDB vector store with a `find_relevant_docs()` function that satisfies `rag_context()` requirements.
- [ ] Replace `_query_rag_for_context` in both writer and editor.
- [ ] Document the new approach in code comments and developer docs.

### Phase 5 – Testing & Replay
- [ ] Add a utility to record Pydantic message logs on demand and replay them via `FunctionModel` in tests.
- [ ] Update CLI scripts to support “record” and “replay” modes without env gymnastics.
- [ ] Append regression tests that load recorded transcripts for smoke runs.

### Phase 6 – Cleanup
- [ ] Drop unused dispatcher/batch code from the Pydantic backend once all agents migrated.
- [ ] Update documentation (README, developer guides) with new instructions.
- [ ] Ensure the CLI environment variables flag the backend choice (`EGREGORA_LLM_BACKEND=legacy|pydantic`).

## Implementation Notes

- **Tool registration:** In tests we disable tool registration (`register_tools=False`) so the `TestModel` stub can return plain text without triggering tool calls.
- **Dependencies injection:** Agents are typed as `Agent[WriterAgentState, WriterAgentReturn]` so tool functions can access run dependencies via `ctx.deps`.
- **Recording:** The writer agent already writes transcripts when `EGREGORA_LLM_RECORD_DIR` is set. Future phases will harmonize this for other agents.
- **Legacy path:** Until migration is complete, the legacy SDK path remains the default; the feature flag only activates the new backend.

## Next Actions

1. Integrate `rag_context()` for the writer agent and update tests accordingly.
2. Port the editor path to Pydantic-AI following the writer pattern.
3. Prepare vector-store helper functions for the RAG integration.
4. Update CLI and docs once writer/editor parity is reached.

This doc should be updated as each phase progresses to keep the team aligned on remaining work.
