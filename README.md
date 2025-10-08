# Egregora

> Automated WhatsApp-to-post pipeline with contextual enrichment, privacy controls, and search-ready archives.

Egregora ingests WhatsApp group exports, anonymises participants, enriches shared links, and publishes human-quality posts. The `egregora` CLI orchestrates ingestion, enrichment, retrieval, and profile generation so that communities receive a daily brief without manual curation.

## Highlights

- **Zero-touch ingestion** – Discover exports locally or sync them from Google Drive before processing, build virtual groups, and skip duplicates automatically via `UnifiedProcessor` and the remote source helper.【F:src/egregora/processor.py†L72-L168】【F:src/egregora/remote_source.py†L55-L113】
- **Context-aware summaries** – Combine anonymised transcripts, enrichment snippets, prior posts, and RAG search hits to create high-signal Markdown posts using the Gemini-based generator.【F:src/egregora/pipeline.py†L64-L266】【F:src/egregora/generator.py†L24-L115】
- **Rich link & media enrichment** – Resolve URLs with Gemini, cache results, and replace WhatsApp attachment markers with publishable paths so posts embed context and media previews out of the box.【F:src/egregora/enrichment.py†L35-L202】【F:src/egregora/processor.py†L209-L313】
- **Participant dossiers** – Incrementally update member profiles whenever activity meets configurable thresholds, producing Markdown dossiers alongside machine-readable history.【F:src/egregora/processor.py†L315-L487】【F:src/egregora/profiles/updater.py†L18-L260】
- **Searchable archive & MCP tooling** – Index generated posts with Gemini embeddings and expose retrieval/search helpers through the RAG utilities and MCP server for downstream tools.【F:src/egregora/rag/index.py†L12-L189】【F:src/egregora/mcp_server/server.py†L87-L355】
- **Privacy-first by default** – Deterministic anonymisation keeps transcripts safe, while the `discover` command lets members compute their pseudonyms independently.【F:src/egregora/anonymizer.py†L16-L132】【F:src/egregora/__main__.py†L142-L197】

## Pipeline at a glance

1. **Discover sources** – Sync optional Google Drive folders, detect WhatsApp exports, and combine them into real or virtual group sources.【F:src/egregora/processor.py†L72-L168】
2. **Normalise daily message frames** – Parse WhatsApp exports into Polars DataFrames, enforce schema/timezone guarantees, and slice per-day transcripts before rendering.【F:src/egregora/parser.py†L20-L150】【F:src/egregora/transcript.py†L12-L154】
3. **Enrich content** – Analyse shared links or media markers with Gemini, store structured insights, and reuse cached analyses to control cost.【F:src/egregora/enrichment.py†L146-L290】【F:src/egregora/cache_manager.py†L16-L142】
4. **Assemble posts** – Blend transcripts, enrichment, RAG snippets, and prior editions into a polished Markdown post per group/day.【F:src/egregora/generator.py†L24-L115】【F:src/egregora/processor.py†L233-L340】
5. **Publish artefacts** – Persist posts, media, and profile dossiers in predictable folders ready for MkDocs publishing or further automation.【F:src/egregora/processor.py†L209-L487】

## Quick start

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) with access to the Gemini models used by the pipeline

### Install & configure

```bash
pip install uv
uv sync
cp egregora.toml.example egregora.toml
export GEMINI_API_KEY="your-api-key"
```

Adjust `egregora.toml` to match your directories, timezone, and enrichment preferences (see [Configuration](#configuration-egregoratoml)).

### Generate your first posts

```bash
# Preview which groups and dates would run
uv run egregora --config egregora.toml --dry-run

# Process the latest two days for every discovered group
uv run egregora --config egregora.toml --days 2
```

Use `--list` to inspect discovered groups, `--no-enrich`/`--no-cache` to toggle enrichment subsystems, `--remote-url` to fetch ZIP exports from a shared Google Drive link, and `--timezone` to override the default run date window.【F:src/egregora/__main__.py†L59-L147】

## Command line interface

### `egregora` (default command)

The root command is equivalent to `egregora process` and accepts the same options:

- `--config / -c` – Load a specific TOML configuration file.
- `--zips-dir` / `--posts-dir` – Override directories at runtime.
- `--remote-url` – Sincroniza exports .zip do Google Drive antes de processar, sem editar o TOML.
- `--days` – Number of recent days to include in each prompt.
- `--disable-enrichment`, `--no-cache`, `--dry-run`, `--list` – Control enrichment, caching, and planning flows.
- `--timezone` – Run the pipeline as if executed in another IANA timezone.

These switches map directly to the Typer options defined in `egregora.__main__`. When run without subcommands the pipeline executes immediately.【F:src/egregora/__main__.py†L20-L138】

### `egregora process`

Explicit subcommand wrapper around the same options, useful when scripting multiple CLI calls or when future subcommands are added.【F:src/egregora/__main__.py†L99-L136】

### `egregora sync`

Synchronise WhatsApp exports from the configured Google Drive folder without running the full pipeline. The command reuses the same configuration loaders as `process`, so `--config`, `--zips-dir`, and related overrides behave identically. Use it in cron jobs to stage new archives ahead of scheduled processing runs or to validate that sharing permissions are correct before generating posts.【F:src/egregora/__main__.py†L138-L213】【F:src/egregora/remote_sync.py†L1-L46】

```bash
# Download archives into the configured directory
uv run egregora sync --config egregora.toml

# Combine with process to stage then render posts
uv run egregora sync --config egregora.toml && \
  uv run egregora process --config egregora.toml --days 2
```

The command posts how many new ZIP archives were discovered and lists their relative paths, making it easy to detect permission or naming issues before invoking `process`.

### `egregora discover`

Calculate deterministic pseudonyms for phone numbers or nicknames so participants can verify how they are represented in posts. Supports `--format` (`human`, `short`, `full`) and `--quiet` for automation-friendly output.【F:src/egregora/__main__.py†L142-L197】

## Configuration (`egregora.toml`)

`PipelineConfig` is powered by Pydantic settings and supports granular tuning of each subsystem.【F:src/egregora/config.py†L210-L371】 Key sections include:

```toml
[zips]
# Optional when using custom overrides; defaults live under data/

[directories]
zips_dir = "data/whatsapp_zips"
posts_dir = "data/posts"
media_url_prefix = "/media"           # Optional public URL when hosting output

[llm]
model = "gemini-flash-lite-latest"
safety_threshold = "BLOCK_NONE"

[enrichment]
enabled = true
relevance_threshold = 2
max_links = 50

[cache]
enabled = true
auto_cleanup_days = 90

[rag]
enabled = true
cache_dir = "cache/rag"

[profiles]
enabled = true
max_profiles_per_run = 3
min_messages = 2

[remote_source]
# Provide a Google Drive share/folder URL to sync exports automatically
#gdrive_url = "https://drive.google.com/drive/folders/..."

[merges.virtual_daily]
name = "Community Digest"
groups = ["core-group", "side-group"]
tag_style = "emoji"
model = "gemini-flash-lite-latest"

[merges.virtual_daily.emojis]
"core-group" = "🌐"
"side-group" = "🛰️"
```

- `directories.*` override where WhatsApp ZIPs and output artefacts live.
- `llm`, `enrichment`, and `cache` tune Gemini usage, enrichment thresholds, and persistent caches.
- `rag` enables post indexing for retrieval-augmented prompts and MCP tooling.
- `profiles` controls when participant dossiers are generated and stored.
- `remote_source.gdrive_url` keeps a Google Drive folder in sync before each run.
- `merges` defines virtual groups combining multiple exports with optional emoji/bracket tagging.【F:src/egregora/config.py†L210-L352】【F:src/egregora/models.py†L10-L32】
- `pipeline.use_dataframe_pipeline` toggles the Polars-first hot path and can be overridden with `EGREGORA_USE_DF_PIPELINE` when you need to fall back to the legacy text flow.【F:src/egregora/config.py†L210-L342】

All options accept environment variable overrides thanks to `pydantic-settings`, enabling reproducible automation setups.【F:src/egregora/config.py†L205-L371】

## Outputs & publishing

During processing the pipeline materialises a predictable directory tree:

- `data/posts/<slug>/daily/YYYY-MM-DD.md` – Generated posts ready for MkDocs or email distribution.
- `data/posts/<slug>/media/` – Deduplicated attachments renamed to deterministic UUIDs for stable links.【F:src/egregora/processor.py†L209-L313】
- `data/posts/<slug>/profiles/` – Markdown dossiers plus JSON archives for participant history.【F:src/egregora/processor.py†L315-L422】
- `cache/` – Disk-backed enrichment cache to avoid reprocessing URLs.【F:src/egregora/cache_manager.py†L16-L142】
- `docs/` – MkDocs site that publishes posts via the Material blog plugin alongside the broader knowledge base (`uv run --extra docs --with ./ mkdocs serve`).

Enable the bundled MkDocs plugins to automate publishing tasks: `tools.mkdocs_build_posts_plugin` regenerates the daily/weekly/monthly archives whenever you run `mkdocs build` or `mkdocs serve`, the language-scoped `blog` plugins from Material surface post feeds/archives, and `tools.mkdocs_media_plugin` exposes media under `/media/<slug>/` when deploying the static site.【F:mkdocs.yml†L56-L74】

## Retrieval & MCP integrations

The Retrieval-Augmented Generation utilities store post embeddings in ChromaDB via `PostRAG` and expose search/list/index maintenance commands through the MCP server. Use them to power chat assistants or IDE integrations.【F:src/egregora/rag/index.py†L12-L189】【F:src/egregora/mcp_server/server.py†L87-L355】

Launch the MCP server via the Typer CLI:

```bash
uv run egregora mcp --config egregora.toml
# Legacy alias retained for automations:
uv run egregora-mcp --config egregora.toml
```

## Custom prompts & filters

Edit the Markdown prompts under `src/egregora/prompts/` to adjust the base system instructions or multi-group behaviour. The pipeline falls back to package resources when custom files are absent, and validates that prompts are never empty.【F:src/egregora/pipeline.py†L64-L115】

Optionally supply `system_message_filters_file` in the configuration to strip templated notifications or bot spam before summarisation.【F:src/egregora/config.py†L222-L229】【F:src/egregora/processor.py†L51-L70】

## Development

- Sync dependencies: `uv sync`
- Run tests: `uv run --with pytest pytest`
- Type-check or explore datasets with `polars` and the utilities under `scripts/`
- Build docs locally: `uv run --extra docs --with ./ mkdocs serve`

The codebase targets Python 3.11+ and relies on `pydantic`, `typer`, and `rich` for configuration and CLI ergonomics.【F:pyproject.toml†L16-L42】

## License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details.
