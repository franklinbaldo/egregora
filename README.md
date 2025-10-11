# Egregora

> Automated WhatsApp-to-post pipeline with contextual enrichment, privacy controls, and search-ready archives.

Egregora ingests WhatsApp group exports, anonymises participants, enriches shared links, and publishes human-quality posts. The `egregora` CLI orchestrates ingestion, enrichment, retrieval, and profile generation so that communities receive a daily brief without manual curation.

## Highlights

- **Zero-touch ingestion** – Discover exports locally, build virtual groups, and skip duplicates automatically via `UnifiedProcessor`.【F:src/egregora/processor.py†L72-L168】
- **Context-aware summaries** – Combine anonymised transcripts, enrichment snippets, prior posts, and RAG search hits to create high-signal Markdown posts using the Gemini-based generator.【F:src/egregora/pipeline.py†L64-L266】【F:src/egregora/generator.py†L24-L115】
- **Rich link & media enrichment** – Resolve URLs with Gemini, cache results, and replace WhatsApp attachment markers with publishable paths so posts embed context and media previews out of the box.【F:src/egregora/enrichment.py†L35-L202】【F:src/egregora/processor.py†L209-L313】
- **Participant dossiers** – Incrementally update member profiles whenever activity meets configurable thresholds, producing Markdown dossiers alongside machine-readable history.【F:src/egregora/processor.py†L315-L487】【F:src/egregora/profiles/updater.py†L18-L260】
- **Privacy-first by default** – Deterministic anonymisation keeps transcripts safe, while the `discover` command lets members compute their pseudonyms independently.【F:src/egregora/anonymizer.py†L16-L132】【F:src/egregora/__main__.py†L142-L197】

## Pipeline at a glance

1. **Discover sources** – Sync optional Google Drive folders, detect WhatsApp exports, and combine them into real or virtual group sources.【F:src/egregora/processor.py†L72-L168】
2. **Normalise daily message frames** – Parse WhatsApp exports into Polars DataFrames, enforce schema/timezone guarantees, and slice per-day transcripts before rendering.【F:src/egregora/parser.py†L20-L150】【F:src/egregora/transcript.py†L12-L154】
3. **Enrich content** – Analyse shared links or media markers with Gemini, store structured insights, and reuse cached analyses to control cost.【F:src/egregora/enrichment.py†L432-L720】【F:src/egregora/processor.py†L41-L116】
4. **Assemble posts** – Blend transcripts, enrichment, RAG snippets, and prior editions into a polished Markdown post per group/day.【F:src/egregora/generator.py†L24-L115】【F:src/egregora/processor.py†L233-L340】
5. **Publish artefacts** – Persist posts, media, and profile dossiers in predictable folders ready for downstream automation or manual review.【F:src/egregora/processor.py†L209-L487】

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

Configuration is now handled via environment variables (see [Configuration](#configuration-via-environment-variables)).

### Generate your first posts

```bash
# Preview which groups and dates would run
uv run egregora process data/whatsapp_zips/*.zip --dry-run

# Process the latest two days for every discovered group
uv run egregora process data/whatsapp_zips/*.zip --days 2
```

Use `--list` to inspect discovered groups, `--no-enrich`/`--no-cache` to toggle enrichment subsystems, and `--timezone` to override the default run date window.【F:src/egregora/__main__.py†L59-L147】

## Linting & formatting

Run the automated formatters locally before pushing to mirror the CI behaviour:

```bash
uv sync --extra lint
uv run pre-commit install
uv run pre-commit run --all-files
```

The CI pipeline re-executes the same hooks, commits any auto-fixable updates back to the source branch, and only fails when an issue requires manual intervention. Installing the hook locally keeps your branches clean and avoids round-trips with the automated fixer.

## Command line interface

### `egregora` (default command)

The root command is equivalent to `egregora process` and accepts the same options:

- `--config / -c` – Load a specific TOML configuration file.
- `--zips-dir` / `--posts-dir` – Override directories at runtime.
- `--days` – Number of recent days to include in each prompt.
- `--disable-enrichment`, `--no-cache`, `--dry-run`, `--list` – Control enrichment, caching, and planning flows.
- `--timezone` – Run the pipeline as if executed in another IANA timezone.

These switches map directly to the Typer options defined in `egregora.__main__`. When run without subcommands the pipeline executes immediately.【F:src/egregora/__main__.py†L20-L138】

### `egregora process`

Explicit subcommand wrapper around the same options, useful when scripting multiple CLI calls or when future subcommands are added.【F:src/egregora/__main__.py†L99-L136】

### `egregora discover`

Calculate deterministic pseudonyms for phone numbers or nicknames so participants can verify how they are represented in posts. Supports `--format` (`human`, `short`, `full`) and `--quiet` for automation-friendly output.【F:src/egregora/__main__.py†L142-L197】

## Configuration via Environment Variables

`PipelineConfig` is powered by Pydantic settings and reads configuration from environment variables. Use the `EGREGORA__` prefix with double underscores to separate nested config sections. Key configuration options include:

```bash
# Basic configuration
export GEMINI_API_KEY="your-api-key"
export EGREGORA__POSTS_DIR="data"

# Profile linking (optional)
export EGREGORA__PROFILES__LINK_MEMBERS_IN_POSTS="true"
export EGREGORA__PROFILES__PROFILE_BASE_URL="/profiles/"

# LLM configuration
export EGREGORA__MODEL="gemini-flash-lite-latest"
export EGREGORA__LLM__SAFETY_THRESHOLD="BLOCK_NONE"

# Enrichment settings
export EGREGORA__ENRICHMENT__ENABLED="true"
export EGREGORA__ENRICHMENT__RELEVANCE_THRESHOLD="2"
export EGREGORA__ENRICHMENT__MAX_LINKS="50"

# Cache settings
export EGREGORA__CACHE__ENABLED="true"
export EGREGORA__CACHE__AUTO_CLEANUP_DAYS="90"

# RAG settings
export EGREGORA__RAG__ENABLED="true"
export EGREGORA__RAG__CACHE_DIR="cache/rag"

# Profile settings
export EGREGORA__PROFILES__ENABLED="true"
export EGREGORA__PROFILES__MAX_PROFILES_PER_RUN="3"
export EGREGORA__PROFILES__MIN_MESSAGES="2"
```

Environment variable configuration uses the `EGREGORA__` prefix with double underscores to separate nested sections:
- `EGREGORA__POSTS_DIR` sets where posts are generated
- `EGREGORA__LLM__*` and `EGREGORA__ENRICHMENT__*` tune Gemini usage and enrichment settings
- `EGREGORA__CACHE__*` and `EGREGORA__RAG__*` control caching and RAG features
- `EGREGORA__PROFILES__*` controls participant profile generation and linking
- All boolean values should be set as `"true"` or `"false"` strings

Configuration is fully handled via environment variables using `pydantic-settings`, enabling reproducible automation setups without requiring configuration files.

## Outputs & publishing

During processing the pipeline materialises a predictable directory tree:

- `data/<slug>/index.md` – Overview page linking recent daily posts and acting as the group landing page.
- `data/<slug>/posts/daily/YYYY-MM-DD.md` – Generated posts ready for publication or email distribution.【F:src/egregora/processor.py†L344-L515】
- `data/<slug>/media/` – Deduplicated attachments renamed to deterministic UUIDs for stable links.【F:src/egregora/media_extractor.py†L44-L188】
- `data/<slug>/profiles/` – Markdown dossiers plus JSON archives for participant history.【F:src/egregora/processor.py†L517-L664】
- `cache/` – Disk-backed enrichment cache to avoid reprocessing URLs.【F:src/egregora/processor.py†L41-L116】【F:src/egregora/enrichment.py†L432-L720】
- `metrics/enrichment_run.csv` – Rolling log with start/end timestamps, relevant counts, domains, and errors for each enrichment run.【F:src/egregora/enrichment.py†L146-L291】
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
- Run tests: `uv run --with pytest pytest`
- Type-check or explore datasets with Polars or a notebook of your choice.

The codebase targets Python 3.11+ and relies on `pydantic`, `typer`, and `rich` for configuration and CLI ergonomics.【F:pyproject.toml†L16-L42】

### CI workflows

- `Request Codex Review`: Comments `@codex code review` on newly opened pull requests via the account associated with the personal access token stored in the `CODEX_REVIEW_TOKEN` repository secret. The workflow authenticates the GitHub CLI with this token (via `GH_TOKEN`) before issuing the comment so it originates from a human-owned account rather than `github-actions`. Use a classic PAT with `public_repo` (or `repo` for private repos) scope.

## License

Egregora is released under the MIT License. See [LICENSE](LICENSE) for details.
