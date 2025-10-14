# Egregora

> Automated WhatsApp-to-post pipeline with contextual enrichment, privacy controls, and search-ready archives.

Egregora ingests WhatsApp group exports, anonymises participants, enriches shared links, and publishes human-quality posts. The `egregora` CLI orchestrates ingestion, enrichment, retrieval, and profile generation so that communities receive a daily brief without manual curation.

## Highlights

- **Local-first ingestion** – Parse WhatsApp exports into Polars DataFrames, enforce schema guarantees, and apply deterministic anonymisation in one pass ready for downstream enrichment.【F:src/egregora/ingest/parser.py†L18-L117】【F:src/egregora/pipeline_runner.py†L44-L90】
- **Gemini embeddings + DuckDB RAG** – Generate vectors with the Gemini API, persist Parquet artefacts, and answer context lookups locally through a DuckDB/VSS index or FastMCP bridge.【F:src/egregora/embed/embed.py†L18-L118】【F:src/egregora/pipeline_runner.py†L130-L160】
- **Jinja-driven generation** – Blend transcripts, enrichment, prior editions, and optional RAG snippets to produce “we”-voiced Markdown posts with reproducible prompts.【F:src/egregora/generate/core.py†L34-L171】【F:src/egregora/generate/cli.py†L24-L144】
- **MkDocs previews out of the box** – Sync generated posts into a docs workspace, run `mkdocs build/serve`, and share live previews without leaving the CLI.【F:src/egregora/static/builder.py†L20-L142】【F:src/egregora/generate/cli.py†L68-L139】
- **Zero-cost archival** – Upload embeddings to the Internet Archive, resume from prior vectors, and toggle uploads directly from the generation flow.【F:src/egregora/archive/uploader.py†L24-L220】【F:src/egregora/generate/cli.py†L139-L188】

## What's new in 1.0.0

- ✅ **Single-command pipeline** – `uv run egregora pipeline …` now routes through a dedicated orchestration layer that chains ingestion, embeddings, local RAG bootstrapping, generation, MkDocs builds, and optional archival in sequence.【F:src/egregora/__main__.py†L118-L219】【F:src/egregora/pipeline_runner.py†L44-L185】
- ✅ **Reusable RAG client** – `LocalRAGClient` embeds queries locally, falls back gracefully when DuckDB VSS is unavailable, and can be injected directly into `_run_generation` or external automation via FastMCP.【F:src/egregora/pipeline_runner.py†L18-L80】【F:src/egregora/generate/cli.py†L24-L196】
- ✅ **Fresh documentation** – New MkDocs guides describe how to configure the DuckDB/Gemini index and run the refactored flow end to end.【F:docs/getting-started/rag-setup.md†L1-L67】【F:docs/getting-started/index.md†L1-L26】
- ✅ **Versioned release** – Package metadata and module exports now report `1.0.0`, signalling the completion of the eight-phase refactor.【F:pyproject.toml†L1-L40】【F:src/egregora/__init__.py†L1-L16】

## Pipeline at a glance

1. **Parse & anonymise** – Extract transcripts from one or many ZIP exports, normalise timestamps, and assign deterministic `Member-XXXX` pseudonyms via Polars expressions.【F:src/egregora/ingest/parser.py†L150-L214】【F:src/egregora/pipeline_runner.py†L44-L90】
2. **Embed conversations** – Call the Gemini embeddings API in batches, attach vector columns, and write Parquet datasets that power later retrieval or archival.【F:src/egregora/embed/embed.py†L43-L95】【F:src/egregora/pipeline_runner.py†L118-L160】
3. **Answer context queries** – Spin up a DuckDB-backed similarity index (with optional VSS extension) and expose it through FastMCP or direct in-process queries.【F:src/egregora/pipeline_runner.py†L132-L160】【F:src/egregora/rag_context/server.py†L12-L91】
4. **Render posts** – Use Jinja templates plus Gemini to craft daily Markdown editions enriched with optional RAG snippets and cached link summaries.【F:src/egregora/generate/core.py†L34-L171】【F:src/egregora/generate/cli.py†L68-L144】
5. **Preview & publish** – Copy posts into a MkDocs workspace, build/serve the static site, and optionally upload embeddings to the Internet Archive for zero-cost persistence.【F:src/egregora/static/builder.py†L20-L142】【F:src/egregora/archive/uploader.py†L24-L220】

## Quick start

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) with access to the Gemini models used by the pipeline

### Install & configure

```bash
pip install uv
uv sync
export GEMINI_API_KEY="your-api-key"
```

Configuration is now handled via explicit CLI arguments (see [CLI Configuration](#cli-configuration)).

### Generate your first posts

```bash
# Run the refactored local-first pipeline end to end
uv run egregora pipeline data/exports/*.zip --days 2 --preview

# Persist the embedding parquet on the Internet Archive after generation
uv run egregora pipeline data/exports/*.zip --archive --archive-suffix nightly
```

The command ingests the provided exports, generates embeddings, boots a local DuckDB index for contextual snippets, renders Markdown posts, builds the MkDocs site, and (optionally) uploads the resulting Parquet artefact.【F:src/egregora/__main__.py†L31-L220】

## Linting & formatting

Run the automated formatters locally before pushing to mirror the CI behaviour:

```bash
uv sync --extra lint
uv run pre-commit install
uv run pre-commit run --all-files
```

The CI pipeline re-executes the same hooks, commits any auto-fixable updates back to the source branch, and only fails when an issue requires manual intervention. Installing the hook locally keeps your branches clean and avoids round-trips with the automated fixer.

## Command line interface

### `egregora pipeline`

Recommended entry-point that chains ingestion, embeddings, RAG lookup, generation, MkDocs previews, and optional archival in a single call. Key options include:

- `--workspace` – Directory where intermediate Parquet files live.
- `--dataset-out` – Override the location of the generated dataset (defaults to `<workspace>/<slug>-<timestamp>.parquet`).
- `--inject-rag/--no-inject-rag` – Toggle the local DuckDB similarity search; combine with `--rag-endpoint` to target a remote FastMCP server instead.【F:src/egregora/__main__.py†L118-L196】
- `--build-static/--no-build-static`, `--preview`, `--preview-host`, `--preview-port` – Control MkDocs builds and live previews.【F:src/egregora/__main__.py†L168-L205】
- `--archive*` flags – Forward the output Parquet to the Internet Archive using the same metadata helpers as the `egregora archive` subcommand.【F:src/egregora/__main__.py†L194-L219】

### `egregora gen`

Render posts from an existing CSV/Parquet dataset. Ideal when datasets are produced elsewhere but you still want the templating, MkDocs, or archival features.【F:src/egregora/generate/cli.py†L24-L196】

### `egregora ingest`, `egregora embed`, `egregora rag`, `egregora archive`

Modular building blocks that expose each phase independently for experimentation or integration into other workflows. All commands share the same configuration surface used by `pipeline` and can be scripted individually.【F:src/egregora/ingest/main.py†L12-L90】【F:src/egregora/embed/cli.py†L12-L120】【F:src/egregora/rag_context/cli.py†L10-L108】【F:src/egregora/archive/cli.py†L15-L138】

## CLI Configuration

Configuration is handled entirely through explicit CLI arguments. No environment variables or configuration files are needed (except `GEMINI_API_KEY` for API access). All options have sensible defaults and can be overridden as needed.

### Basic Usage

```bash
# Generate posts with defaults
export GEMINI_API_KEY="your-api-key"
uv run egregora pipeline data/exports/*.zip

# Generate with custom options
uv run egregora pipeline data/exports/*.zip \
  --workspace tmp/egregora \
  --dataset-out artifacts/dataset.parquet \
  --days 3 \
  --build-static \
  --archive --archive-identifier egregora-demo
```

### Available Options

Run `uv run egregora pipeline --help` to see all available options. Highlights:

- **Input/Output**: `--workspace`, `--dataset-out`, `--output`, `--template`, `--previous-post`.
- **Date Range**: `--days`, `--from-date`, `--to-date`.
- **Retrieval**: `--inject-rag/--no-inject-rag`, `--rag-endpoint`, `--rag-top-k`, `--rag-min-similarity`.
- **Static site**: `--build-static/--no-build-static`, `--preview`, `--preview-host`, `--preview-port`.
- **Archival**: `--archive`, `--archive-identifier`, `--archive-suffix`, `--archive-meta`.
- All configuration is explicit and transparent—no hidden environment variables beyond the Gemini API credentials.

## Outputs & publishing

The refactored pipeline keeps its artefacts simple:

- A consolidated Parquet dataset with embeddings (defaults to `tmp-tests/pipeline/<slug>-<timestamp>.parquet`).
- Markdown posts written to `docs/posts/` (or to the `--output` directory), prontos para MkDocs/GitHub Pages.【F:src/egregora/generate/cli.py†L76-L153】
- Opcionalmente, um site estático recompilado em `site/` quando `--build-static` ou `--preview` é utilizado.【F:src/egregora/static/builder.py†L41-L171】

Os diretórios de cache legados e dossiês de perfis foram removidos junto com o processador monolítico. O foco agora é o fluxo enxuto dataset → embeddings → MkDocs com suporte opcional a arquivamento.

## Retrieval utilities

The Retrieval-Augmented Generation helpers store post embeddings in ChromaDB via `PostRAG` for use in bespoke automations or exploratory notebooks.【F:src/egregora/rag/index.py†L12-L189】 Use the runtime API directly to refresh or inspect the index whenever new posts are generated.

### Rebuild the RAG index via the current CLI

Rebuild or refresh the embeddings with the existing CLI/runtime surface—no
dedicated helper script required:

```bash
# Force a clean rebuild of the post embeddings
uv run python - <<'PY'
from pathlib import Path

from egregora.rag.config import RAGConfig
from egregora.rag.index import PostRAG

rag = PostRAG(
    posts_dir=Path("data/posts"),
    cache_dir=Path("cache/rag"),
    config=RAGConfig(enabled=True, vector_store_type="chroma"),
)
result = rag.update_index(force_rebuild=True)
print("Rebuilt", result["posts_count"], "posts →", result["chunks_count"], "chunks")
PY
```

Adjust the directories or `RAGConfig` arguments to match your deployment. The
same pattern works inside automations or GitHub Actions, eliminating the need
for bespoke one-off scripts.

## Custom prompts & filters

Edit the Markdown prompts under `src/egregora/prompts/` to adjust the base system instructions or multi-group behaviour. The pipeline falls back to package resources when custom files are absent, and validates that prompts are never empty.【F:src/egregora/pipeline.py†L64-L115】

Keyword extraction and system-message filtering now rely on LLM adapters instead of brittle phrase lists. Configure model credentials through the regular pipeline settings and provide custom keyword providers when embedding the library in other tooling.【F:src/egregora/rag/query_gen.py†L17-L60】【F:src/egregora/system_classifier.py†L39-L196】

## Development

- Sync dependencies: `uv sync`
  - The uv-managed environment now pre-installs the testing and docs toolchain declared under `tool.uv.dev-dependencies`, so the
    common commands below work without extra flags.
- Run tests: `uv run pytest`
- Type-check or explore datasets with Polars or a notebook of your choice.

The codebase targets Python 3.11+ and relies on `pydantic`, `typer`, and `rich` for configuration and CLI ergonomics.【F:pyproject.toml†L16-L42】

### CI workflows

- `Request Codex Review`: Comments `@codex code review` on newly opened pull requests via the account associated with the personal access token stored in the `CODEX_REVIEW_TOKEN` repository secret. The workflow authenticates the GitHub CLI with this token (via `GH_TOKEN`) before issuing the comment so it originates from a human-owned account rather than `github-actions`. Use a classic PAT with `public_repo` (or `repo` for private repos) scope.

## License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details.
