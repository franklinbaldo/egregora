# Egregora v3 ETL Plan

v3 frames the WhatsApp → knowledge flow as a classic ETL (Extract ➜ Transform ➜ Load) pipeline powered by DuckDB + ibis. Each workstream maps to one phase so we can evolve components independently without losing sight of the overall pipeline.

## Goals
- Deliver a fully ibis/DuckDB-first pipeline (no pandas) that scales from local to hosted environments.
- Provide a Typer CLI that orchestrates each ETL phase (`eg3 ingest`, `eg3 build`, `eg3 query`, etc.).
- Maintain parity with v2 anonymization/writer behaviour while enabling richer analytics downstream.

## ETL Phases

### Extract
- [x] Read Parquet exports without pandas (DuckDB `read_parquet`).
- [ ] Ingest zipped WhatsApp exports end-to-end (staging + metadata capture).
- [ ] Validate incoming schemas and surface actionable error messages.

### Transform
- [x] Anonymize and ingest messages via ibis dataframes.
- [x] Support ANN fallback (`vss_search` → `vss_match`) with automatic retries.
- [ ] Add async batch embedding for large corpora.
- [ ] Build an ANN vs exact evaluation harness to track recall/precision impacts.

### Load
- [ ] Persist staged data into versioned DuckDB datasets (partition by date / group).
- [x] Expose Typer commands to rebuild embeddings (`eg3 build`) and query them (`eg3 query`).
- [ ] Generate MkDocs-ready markdown (posts/profiles) through ibis-driven writers.

## CLI & Developer Experience
- [x] Group Typer commands (`init`, `ingest`, `build`, `query`, `rank`, `site`, `import`).
- [ ] Add rich progress indicators/logging for long ETL jobs.
- [ ] Provide a `--dry-run` flag to preview ETL effects without writing output.
- [x] Track a `v3` extras group in `pyproject.toml` for ibis/DuckDB requirements.

## Documentation & Tooling
- [ ] Author a dedicated `v3/README.md` with ETL-focused quickstart instructions.
- [ ] Update contribution guidelines to reflect ibis/DuckDB workflows.
- [ ] Publish notebooks or scripts demonstrating end-to-end ETL runs.

## Next Steps
1. Implement zip extraction + staging for the Extract phase.
2. Build the ANN evaluation harness and integrate metrics into CI.
3. Draft the v3 README and update docs navigation to highlight the ETL flow.
