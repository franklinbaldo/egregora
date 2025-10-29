# Egregora Pruning Plan

## Objectives
- Preserve the complete "parse → anonymize → enrich → write" journey exposed by `egregora init` and `egregora process` while reducing friction for contributors.
- Consolidate optional subsystems (ranking, editor, RAG) behind clearer extension points so they remain available without bloating the default runtime.
- Update tooling, docs, and tests so maintainers can iterate faster without risking regressions in current functionality.

## Current Footprint Snapshot
| Area | Representative files | Notes |
| --- | --- | --- |
| Core pipeline | `src/egregora/pipeline.py`, `src/egregora/writer.py`, `src/egregora/parser.py`, `src/egregora/anonymizer.py` | Executes the primary WhatsApp → MkDocs flow and orchestrates enrichment hooks. |
| Optional CLI flows | `src/egregora/cli.py` (`rank`, `edit` commands) | Share configuration models and logging helpers but have accumulated bespoke code paths. |
| RAG system | `src/egregora/rag/`, helpers inside `writer.py`, `pipeline.py`, and `enricher.py` | Provides media/post retrieval and feeds both the editor and ranking flows. |
| Ranking subsystem | `src/egregora/ranking/`, supporting prompts and storage | Maintains ELO comparisons and Typer session helpers. |
| Interactive editor | `src/egregora/editor.py`, `src/egregora/editor_agent.py` | Drives iterative editing with Gemini orchestration and RAG lookups. |
| Documentation/tests | `docs/features/*.md`, `docs/reference/*.md`, `tests/test_rag_store.py`, `tests/test_writer.py`, etc. | Capture the expected behaviors of all features; some guides duplicate effort across modules. |

## Proposed Pruning Waves

### Wave 1 – Establish a modular baseline
Clarify boundaries between the core pipeline and optional extensions so that each subsystem can evolve independently without being treated as dead weight.

:::task-stub{title="Carve out explicit extension points"}
1. Introduce an `egregora.extensions` package that exposes registration hooks for ranking, editor, and RAG capabilities.
   - Keep the API lightweight by defining a `SupportsExtension` typing `Protocol` that only requires `register_cli(typer_app)` and `register_pipeline(pipeline)` callables, so features can implement the contract without inheritance or additional scaffolding.
2. Move feature-specific setup (Typer subcommands, dependency wiring) behind those hooks while keeping the existing commands functional.
   - Example: migrate the current `rank` command by providing a small `RankingExtension` dataclass that satisfies the `SupportsExtension` protocol and wraps existing `RankingSession` helpers internally.
3. Document the extension surface in `docs/reference/extensions.md` and add architectural diagrams so contributors see how to add or modify features without touching the core pipeline.
   - Include a short code sample showing how a hypothetical `TranslateExtension` would plug into the same hook, demonstrating non-regression for future additions.
:::

### Wave 2 – Reduce duplication across CLIs and configs
Simplify shared configuration while maintaining parity for all commands.

:::task-stub{title="Unify configuration schemas"}
1. Refactor `src/egregora/config_types.py` so common fields are defined once and reused across ranking, editor, and processing configs.
   - Replace duplicated `ModelSettings` declarations with a single dataclass consumed by `ProcessingConfig`, `EditorConfig`, and `RankingConfig`.
2. Extract shared CLI utilities (`prompt_for_zip`, `load_context`, etc.) into `src/egregora/cli_common.py` to eliminate copy/paste logic.
   - Provide a usage example in the docstring demonstrating how `egregora rank` and `egregora edit` import the helper to load `settings.yaml`.
3. Update `tests/test_cli_config.py` and similar suites to assert the unified config behavior for every command, ensuring no capability regresses.
   - Add fixtures that instantiate each CLI with representative configs (e.g., `tests/fixtures/ranking_config.yaml`) and assert parity with current defaults.
:::

### Wave 3 – Streamline the RAG pipeline without disabling it
Focus on performance and ergonomics while preserving enrichment results.

:::task-stub{title="Optimize RAG data flow"}
1. Profile vector store operations in `src/egregora/rag/` and cache expensive lookups via `src/egregora/cache.py` so enrichment remains responsive.
   - Capture baseline timings (e.g., `python -m egregora.rag.benchmark sample.db`) and commit the script so future runs can verify improvements.
2. Extract common DuckDB bootstrapping into a single module and gate optional dependencies behind lazy imports to cut startup overhead.
   - Provide a concrete example where `rag/store.py` imports `duckdb` only when `RAGExtension` is initialized, avoiding regressions for CLI-only users.
3. Extend `tests/test_rag_store.py` with performance-focused assertions (e.g., ensuring warm cache hits) to verify that functionality still works end-to-end.
   - Include a regression test that loads the editor with the cache enabled and asserts the same document count as before, proving functionality parity.
:::

### Wave 4 – Tighten dependency management and packaging
Keep the feature set intact while making optional pieces truly optional.

:::task-stub{title="Right-size dependency groups"}
1. Split `pyproject.toml` extras into `core`, `rag`, `editor`, and `ranking` so users install only what they need without losing access to features.
   - For example, move `rank-bm25` into the `ranking` extra and document the install command `uv pip install ".[ranking]"` alongside existing CLI usage.
2. Update `uv.lock` and documentation to reflect the new extras, making sure default installs continue to pass the existing CLI smoke tests.
   - Run `uv sync --extra rag --extra editor` during CI and capture the command outputs to show which features were validated.
3. Add CI checks that install each extra in isolation and run the relevant subset of tests to guarantee ongoing compatibility.
   - Extend the GitHub Actions workflow with matrix entries (`extra=rag|editor|ranking`) and surface the logs in `docs/maintenance/ci-matrix.md` as an operational example.
:::

### Wave 5 – Refresh documentation and tests around the leaner architecture
Ensure that guidance and coverage align with the refactored structure while demonstrating that no capabilities were dropped.

:::task-stub{title="Document and validate the preserved feature set"}
1. Rewrite `README.md`, `docs/getting-started/quickstart.md`, and feature guides to explain the new extension architecture and how to enable ranking, editor, and RAG flows.
   - Embed a `Quick install` table that maps each feature to the exact command (`uvx egregora rank --config samples/ranking.yaml`) so usage remains explicit.
2. Add end-to-end golden tests for `egregora process`, `egregora rank`, and `egregora edit` to confirm the features still behave as documented.
   - Store reference outputs under `tests/golden/` and include comparisons against the pre-refactor fixtures to prevent unnoticed regressions.
3. Update changelog entries to clarify that the work improved modularity and packaging without removing functionality, highlighting migration tips where file locations changed.
   - Provide before/after path examples (e.g., `src/egregora/editor.py` → `src/egregora/extensions/editor/__init__.py`) so adopters know where to update imports.
:::

## Validation Checklist
- Run `pytest` (full suite and feature-specific subsets) to guarantee that all commands continue to work after refactors.
- Execute `egregora init demo-site`, `egregora process <sample.zip> --output=demo-site`, `egregora rank`, and `egregora edit` to manually confirm parity with current behavior.
- Build documentation (`uvx --with mkdocs-material mkdocs build`) to ensure extension guides render correctly and contain no dead links.

## Risks & Mitigations
- **Hidden coupling:** Introducing extension hooks may surface previously implicit dependencies; mitigate by adding integration tests that load each extension in isolation.
- **Dependency drift:** Splitting extras can leave transitive requirements unpinned; use `uv pip check` and weekly dependency audits to keep environments healthy.
- **Contributor confusion:** Provide code walkthroughs and diagrams in the docs so new contributors know features still exist but live behind the new modular boundaries.
