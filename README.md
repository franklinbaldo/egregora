# Egregora

> Automated WhatsApp-to-post pipeline with contextual enrichment, privacy controls, and search-ready archives.

Egregora ingests WhatsApp group exports, anonymises participants, enriches shared links, and publishes human-quality posts. The `egregora` CLI orchestrates ingestion, enrichment, retrieval, and profile generation so that communities receive a daily brief without manual curation.

## Highlights

- **Zero-touch ingestion** – Discover exports locally, build virtual groups automatically
- **Historical awareness** – RAG retrieves relevant past discussions for narrative continuity
- **Intellectual context** – Profile system tracks participant expertise and thinking styles
- **Context-aware summaries** – Generator combines temporal + intellectual context
- **Rich link & media enrichment** – Gemini analyzes shared content for deeper insights
- **Privacy-first by default** – Deterministic anonymization keeps transcripts safe

## How It Works

Egregora builds **three layers of context** for post generation:

### 1. Historical Context (RAG)
**What the group discussed before**
- Automatically indexes all generated posts
- Retrieves top-3 most relevant past discussions
- Enables references like "continuing our debate from March..."

### 2. Intellectual Context (Profiles)
**Who's speaking and their background**
- Tracks participant expertise, thinking styles, and evolution
- Updates incrementally as more data is available
- Enables contextual attribution like "Member-ABCD brought their usual philosophical perspective..."

### 3. Immediate Context (Today's Messages)
**What's being discussed right now**
- Parsed, anonymized, enriched WhatsApp transcripts
- Link analysis and media context
- Previous day's post for continuity

### The Magic: All Three Together

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

## CLI Configuration

Configuration is handled entirely through explicit CLI arguments. No environment variables or configuration files are needed (except `GEMINI_API_KEY` for API access). All options have sensible defaults and can be overridden as needed.

### Basic Usage

```bash
# Generate posts with defaults
export GEMINI_API_KEY="your-api-key"
uv run egregora process data/whatsapp_zips/*.zip

# Generate with custom options
uv run egregora process data/whatsapp_zips/*.zip \
  --output data/output \
  --model gemini-flash-lite-latest \
  --timezone America/Porto_Velho \
  --days 2
```

### Profile Linking

```bash
# Enable profile linking (default: enabled)
uv run egregora process data/whatsapp_zips/*.zip \
  --link-profiles \
  --profile-base-url "/profiles/"

# Disable profile linking
uv run egregora process data/whatsapp_zips/*.zip \
  --no-link-profiles
```

### Advanced Configuration

```bash
# Full configuration example
uv run egregora process data/whatsapp_zips/*.zip \
  --output data/custom-output \
  --model gemini-flash-lite-latest \
  --timezone America/Porto_Velho \
  --days 7 \
  --link-profiles \
  --profile-base-url "/profiles/" \
  --safety-threshold BLOCK_NONE \
  --thinking-budget -1 \
  --max-links 50 \
  --relevance-threshold 2 \
  --cache-dir cache \
  --auto-cleanup-days 90
```

### Available Options

Run `uv run egregora process --help` to see all available options:

- **Input/Output**: `--output`, `--group-name`, `--group-slug`
- **Model Settings**: `--model`, `--safety-threshold`, `--thinking-budget`
- **Date Range**: `--days`, `--from-date`, `--to-date`, `--timezone`
- **Features**: `--disable-enrichment`, `--no-cache`, `--link-profiles`
- **Profile Linking**: `--profile-base-url`
- **Enrichment**: `--max-links`, `--relevance-threshold`
- **Cache**: `--cache-dir`, `--auto-cleanup-days`
- **Debug**: `--list`, `--dry-run`

All configuration is explicit and transparent - no hidden dependencies on environment variables or configuration files.

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
