# Egregora

> Automated WhatsApp-to-newsletter pipeline with contextual enrichment, privacy controls, and search-ready archives.

Egregora ingests WhatsApp group exports, anonymises participants, enriches shared links, and publishes human-quality newsletters. The `egregora` CLI orchestrates ingestion, enrichment, retrieval, and profile generation so that communities receive a daily brief without manual curation.

## Highlights

- **Zero-touch ingestion** – Discover exports locally or sync them from Google Drive before processing, build virtual groups, and skip duplicates automatically via `UnifiedProcessor` and the remote source helper.【F:src/egregora/processor.py†L72-L168】【F:src/egregora/remote_source.py†L55-L113】
- **Context-aware summaries** – Combine anonymised transcripts, enrichment snippets, prior newsletters, and RAG search hits to create high-signal Markdown reports using the Gemini-based generator.【F:src/egregora/pipeline.py†L64-L266】【F:src/egregora/generator.py†L24-L115】
- **Rich link & media enrichment** – Resolve URLs with Gemini, cache results, and replace WhatsApp attachment markers with publishable paths so newsletters embed context and media previews out of the box.【F:src/egregora/enrichment.py†L35-L202】【F:src/egregora/processor.py†L209-L313】
- **Participant dossiers** – Incrementally update member profiles whenever activity meets configurable thresholds, producing Markdown dossiers alongside machine-readable history.【F:src/egregora/processor.py†L315-L487】【F:src/egregora/profiles/updater.py†L18-L260】
- **Searchable archive & MCP tooling** – Index generated newsletters with Gemini embeddings and expose retrieval/search helpers through the RAG utilities and MCP server for downstream tools.【F:src/egregora/rag/index.py†L12-L189】【F:src/egregora/mcp_server/server.py†L87-L355】
- **Privacy-first by default** – Deterministic anonymisation keeps transcripts safe, while the `discover` command lets members compute their pseudonyms independently.【F:src/egregora/anonymizer.py†L16-L132】【F:src/egregora/__main__.py†L142-L197】

## Pipeline at a glance

1. **Discover sources** – Sync optional Google Drive folders, detect WhatsApp exports, and combine them into real or virtual group sources.【F:src/egregora/processor.py†L72-L168】
2. **Extract daily transcripts** – Parse, anonymise, and consolidate daily conversations while tracking per-day activity stats.【F:src/egregora/pipeline.py†L125-L220】【F:src/egregora/transcript.py†L12-L205】
3. **Enrich content** – Analyse shared links or media markers with Gemini, store structured insights, and reuse cached analyses to control cost.【F:src/egregora/enrichment.py†L146-L290】【F:src/egregora/cache_manager.py†L16-L142】
4. **Assemble newsletters** – Blend transcripts, enrichment, RAG snippets, and prior editions into a polished Markdown report per group/day.【F:src/egregora/generator.py†L24-L115】【F:src/egregora/processor.py†L233-L340】
5. **Publish artefacts** – Persist newsletters, media, and profile dossiers in predictable folders ready for MkDocs publishing or further automation.【F:src/egregora/processor.py†L209-L487】

## Quick start

### Requirements

- Python 3.10+
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

### Generate your first newsletters

```bash
# Preview which groups and dates would run
uv run egregora --config egregora.toml --dry-run

# Process the latest two days for every discovered group
uv run egregora --config egregora.toml --days 2
```

Use `--list` to inspect discovered groups, `--no-enrich`/`--no-cache` to toggle enrichment subsystems, and `--timezone` to override the default run date window.【F:src/egregora/__main__.py†L59-L131】

## Command line interface

### `egregora` (default command)

The root command is equivalent to `egregora process` and accepts the same options:

- `--config / -c` – Load a specific TOML configuration file.
- `--zips-dir` / `--newsletters-dir` – Override directories at runtime.
- `--days` – Number of recent days to include in each prompt.
- `--disable-enrichment`, `--no-cache`, `--dry-run`, `--list` – Control enrichment, caching, and planning flows.
- `--timezone` – Run the pipeline as if executed in another IANA timezone.

These switches map directly to the Typer options defined in `egregora.__main__`. When run without subcommands the pipeline executes immediately.【F:src/egregora/__main__.py†L20-L138】

### `egregora process`

Explicit subcommand wrapper around the same options, useful when scripting multiple CLI calls or when future subcommands are added.【F:src/egregora/__main__.py†L99-L136】

### `egregora discover`

Calculate deterministic pseudonyms for phone numbers or nicknames so participants can verify how they are represented in newsletters. Supports `--format` (`human`, `short`, `full`) and `--quiet` for automation-friendly output.【F:src/egregora/__main__.py†L142-L197】

## Configuration (`egregora.toml`)

`PipelineConfig` is powered by Pydantic settings and supports granular tuning of each subsystem.【F:src/egregora/config.py†L210-L371】 Key sections include:

```toml
[zips]
# Optional when using custom overrides; defaults live under data/

[directories]
zips_dir = "data/whatsapp_zips"
newsletters_dir = "data/newsletters"
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
- `rag` enables newsletter indexing for retrieval-augmented prompts and MCP tooling.
- `profiles` controls when participant dossiers are generated and stored.
- `remote_source.gdrive_url` keeps a Google Drive folder in sync before each run.
- `merges` defines virtual groups combining multiple exports with optional emoji/bracket tagging.【F:src/egregora/config.py†L210-L352】【F:src/egregora/models.py†L10-L32】

All options accept environment variable overrides thanks to `pydantic-settings`, enabling reproducible automation setups.【F:src/egregora/config.py†L205-L371】

## Outputs & publishing

During processing the pipeline materialises a predictable directory tree:

- `data/newsletters/<slug>/daily/YYYY-MM-DD.md` – Generated newsletters ready for MkDocs or email distribution.
- `data/newsletters/<slug>/media/` – Deduplicated attachments renamed to deterministic UUIDs for stable links.【F:src/egregora/processor.py†L209-L313】
- `data/newsletters/<slug>/profiles/` – Markdown dossiers plus JSON archives for participant history.【F:src/egregora/processor.py†L315-L422】
- `cache/` – Disk-backed enrichment cache to avoid reprocessing URLs.【F:src/egregora/cache_manager.py†L16-L142】
- `docs/` – MkDocs site that can publish newsletters and reports (`uv run mkdocs serve`).

Enable the bundled MkDocs plugin (`tools.mkdocs_media_plugin`) to expose media under `/media/<slug>/` when deploying the static site.【F:mkdocs.yml†L1-L74】

## Retrieval & MCP integrations

The Retrieval-Augmented Generation utilities store newsletter embeddings in ChromaDB via `NewsletterRAG` and expose search/list/index maintenance commands through the MCP server. Use them to power chat assistants or IDE integrations.【F:src/egregora/rag/index.py†L12-L189】【F:src/egregora/mcp_server/server.py†L87-L355】

Launch the MCP server directly:

```bash
uv run python -m egregora.mcp_server --config egregora.toml
```

## Custom prompts & filters

Edit the Markdown prompts under `src/egregora/prompts/` to adjust the base system instructions or multi-group behaviour. The pipeline falls back to package resources when custom files are absent, and validates that prompts are never empty.【F:src/egregora/pipeline.py†L64-L115】

Optionally supply `system_message_filters_file` in the configuration to strip templated notifications or bot spam before summarisation.【F:src/egregora/config.py†L222-L229】【F:src/egregora/processor.py†L51-L70】

## Development

- Sync dependencies: `uv sync`
- Run tests: `uv run --with pytest pytest`
- Type-check or explore datasets with `polars` and the utilities under `scripts/`
- Build docs locally: `uv run --with docs mkdocs serve`

The codebase targets Python 3.10+ and relies on `pydantic`, `typer`, and `rich` for configuration and CLI ergonomics.【F:pyproject.toml†L16-L42】

## License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details.
