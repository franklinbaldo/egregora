# Egregora v3 Implementation Plan

This plan outlines the steps to implement Egregora v3 based on the greenfield plan.

## Phase 1: Project Scaffolding and Core Components

1.  **Create New Directory Structure**:
    *   Create the `src/egregora_v3` directory.
    *   Inside `src/egregora_v3`, create the following subdirectories: `core`, `adapters`, `features`, `cli`, and `tests`.
    *   Inside `src/egregora_v3/adapters`, create `embeddings` and `vectorstore`.
    *   Inside `src/egregora_v3/features`, create `rag`, `ranking`, and `site`.

2.  **Move Unchanged Anonymization Logic**:
    *   Identify the current anonymization logic from `src/egregora/`.
    *   Move the relevant files into `src/egregora_v3/adapters/privacy/anonymize.py` without any changes.

3.  **Implement Core Modules**:
    *   `core/paths.py`: Define XDG-aware application paths for data, logs, and cache.
    *   `core/config.py`: Implement configuration loading with `egregora.toml`, environment variables, and CLI overrides. Use Pydantic for settings management.
    *   `core/db.py`: Set up DuckDB connection management and DDL execution. This will contain the DDL for `rag_chunks`, `rag_vectors`, and ranking tables.
    *   `core/types.py`: Define shared data types and Pydantic models.
    *   `core/logging.py`: Configure logging for the application.
    *   `core/context.py`: Implement the `Context` class that ties together the database connection, embedding client, and vector store.

4.  **Implement `init` and `doctor` CLI commands**:
    *   `cli/app.py`: Set up the main Typer application.
    *   Implement `eg3 init`: This command will create the database, load extensions (like VSS), and run the DDL from `core/db.py`.
    *   Implement `eg3 doctor`: This command will report on the health of the system, including table counts, embedding dimensions, index parameters, and a checksum of the anonymization code.

## Phase 2: RAG Pipeline Implementation and Testing

5.  **Anonymization Parity Tests**:
    *   Create golden data from the v2 anonymization logic.
    *   Write tests for the moved anonymization logic in `tests/adapters/privacy/` to ensure byte-for-byte identical output with the golden data.

6.  **Implement RAG Ingestion**:
    *   `features/rag/ingest.py`: Implement the logic for ingesting data.
    *   This will involve parsing a source, running the anonymization step, and writing the data to the `rag_chunks` table in DuckDB.
    *   `cli/app.py`: Add the `eg3 ingest` command.

7.  **Implement RAG Build Process**:
    *   `adapters/embeddings/gemini.py`: Implement the Gemini embedding client.
    *   `adapters/vectorstore/duckdb_vss.py`: Implement the DuckDB VSS vector store wrapper.
    *   `features/rag/build.py`: Implement logic to embed chunks from `rag_chunks` and upsert them into `rag_vectors`. This will also build the VSS index.
    *   `cli/app.py`: Add the `eg3 build` command.

8.  **Implement RAG Querying**:
    *   `features/rag/query.py`: Implement the query logic supporting both "exact" (brute-force) and "ann" (VSS index) modes.
    *   `cli/app.py`: Add the `eg3 query` command.

9.  **RAG Pipeline Integration Tests**:
    *   Write end-to-end tests for the RAG pipeline: `ingest` -> `build` -> `query`.
    *   Create retrieval sanity tests to compare the overlap between "ann" and "exact" query results, ensuring it's above a certain threshold.

## Phase 3: Ranking, Site Generation, and Finalization

10. **Implement Ranking Feature**:
    *   `features/ranking/duel.py`: Implement the logic for ELO-style duels.
    *   `features/ranking/export.py`: Implement logic to export ranking data.
    *   `cli/app.py`: Add `eg3 rank duel` and `eg3 rank export` commands.
    *   Write tests for the ranking functionality.

11. **Implement Site Generation**:
    *   `features/site/render.py`: Port the minimal logic required for site generation.
    *   `cli/app.py`: Add the `eg3 site render` command.
    *   Write tests for site generation.

12. **Implement Optional Importer**:
    *   `cli/app.py`: Add the `eg3 import parquet` command for migrating v2 data.
    *   This command will re-embed existing anonymized text and build the VSS index.
    *   Write tests for the importer.

13. **Documentation and CI**:
    *   Update the README and other documentation to reflect the new v3 architecture, CLI, and usage.
    *   Ensure the CI pipeline is updated to run `ruff`, `mypy`, and the full `pytest` suite for v3. Include the anonymization checksum check in CI.

## Phase 4: Test Suite Development

14. **Write Comprehensive Test Suite**:
    *   As requested, the next step after this plan is to write the test files. This will be a separate phase of work.
    *   Tests will be written for each component, ensuring all quality gates from the manifesto are met.
    *   This includes unit tests for core components, integration tests for features, and end-to-end tests for CLI commands.
