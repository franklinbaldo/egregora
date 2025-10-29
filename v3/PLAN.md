# Egregora v3 Plan

## Goals
- Deliver a fully ibis/DuckDB-first ingestion and RAG pipeline without pandas.
- Provide a user-friendly Typer CLI that scaffolds, ingests, builds, and queries with minimal setup.
- Maintain parity with v2 anonymization and writer behaviour while exploring v3 features.

## Workstreams

### 1. Data Ingestion & Storage
- [x] Ingest Parquet exports without pandas (use DuckDB `read_parquet`).
- [ ] Support direct zip ingestion for v3 pipelines.
- [ ] Add validations for schema mismatches.

### 2. Embeddings & Vector Store
- [x] DuckDB VSS fallback between `vss_search` and `vss_match`.
- [ ] Async batch embedding for large corpora.
- [ ] Evaluation harness for ANN accuracy vs exact search.

### 3. CLI Experience
- [x] Group Typer commands (`init`, `ingest`, `build`, `query`, `rank`, `site`, `import`).
- [ ] Add rich progress output for long-running tasks.
- [ ] Provide `--dry-run` option for ingest/build commands.

### 4. Documentation & Tooling
- [ ] Author v3 README with quickstart.
- [ ] Update contribution guidelines for ibis-first workflows.
- [x] Track v3 extra in `pyproject.toml`.
- [ ] Publish example notebooks demonstrating v3 pipeline end-to-end.

## Next Steps
1. Implement zip ingestion for v3 (`egregora_v3.features.ingest`).
2. Build RAG quality evaluation harness (compare ANN vs exact).
3. Draft v3 README and update docs navigation structure.
