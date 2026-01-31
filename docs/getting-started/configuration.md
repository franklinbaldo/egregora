# Configuration

!!! tip "For Most Users"
    You probably don't need to read this page! Egregora is designed to work with **zero configuration** for 95% of users. The defaults are carefully chosen to create beautiful results automatically.

**MODERN (Phase 2-4)**: Egregora configuration lives in `.egregora.toml`, separate from rendering (MkDocs).

Configuration sources (priority order):
1. **CLI arguments** - Highest priority (one-time overrides)
2. **Environment variables** - `EGREGORA_SECTION__KEY` (e.g., `EGREGORA_MODELS__WRITER`)
3. **`.egregora.toml`** - Main configuration file
4. **Defaults** - Defined in Pydantic `EgregoraConfig` model

## CLI Configuration

The `egregora write` command accepts many options:

```bash
egregora write [OPTIONS] EXPORT_PATH
```

### Core Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Output directory for blog | `site` |
| `--timezone` | Timezone for message timestamps | `None` |
| `--step-size` | Size of each processing window | `1` |
| `--step-unit` | Unit: `messages`, `hours`, `days`, `bytes` | `days` |
| `--from-date` | Start date (YYYY-MM-DD) | `None` |
| `--to-date` | End date (YYYY-MM-DD) | `None` |

### Model Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | Override LLM model for all tasks | `None` |

### Feature Flags

| Option | Description | Default |
|--------|-------------|---------|
| `--enable-enrichment/--no-enable-enrichment` | Enable AI enrichment (images, links) | `True` |

## Environment Variables

**MODERN**: Only credentials live in environment variables (keep out of git).

```bash
export GOOGLE_API_KEY="your-gemini-api-key"  # Required for Gemini API
export OPENROUTER_API_KEY="your-openrouter-key"  # Optional
```

## .egregora.toml

**MODERN (Phase 2-4)**: Main configuration file (maps to Pydantic `EgregoraConfig` model).

Generated automatically by `egregora init` or `egregora write` on first run:

```toml
# Model configuration (pydantic-ai format: provider:model-name)
[models]
writer = "google-gla:gemini-flash-latest"
enricher = "google-gla:gemini-flash-latest"
enricher_vision = "google-gla:gemini-flash-latest"
embedding = "models/text-embedding-004"
ranking = "google-gla:gemini-flash-latest"      # Optional
editor = "google-gla:gemini-flash-latest"       # Optional

# RAG (Retrieval-Augmented Generation) settings
[rag]
enabled = true
top_k = 5                    # Number of results to retrieve
min_similarity_threshold = 0.7         # Minimum similarity threshold (0-1)

# Writer agent settings
[writer]
custom_instructions = """
Write in a casual, friendly tone inspired by longform journalism.
"""
# enable_banners is now implicitly controlled by availability of 'banner' model and feature flags

# Enrichment settings
[enrichment]
enabled = true
enable_url = true
enable_media = true
max_enrichments = 50

# Pipeline windowing settings
[pipeline]
step_size = 1                # Size of each window
step_unit = "days"           # "messages", "hours", "days", "bytes"
overlap_ratio = 0.2          # Window overlap (0.0-0.5)

# Feature flags
[features]
ranking_enabled = false
annotations_enabled = true
```

**Location**: `.egregora.toml` in site root (next to `mkdocs.yml`)

### Sites and sources (multi-site configs)

You can now register multiple data inputs and publishing targets in a single `.egregora.toml`. Define reusable sources once, then map them to one or more sites:

```toml
[sources.whatsapp_export]
type = "whatsapp"               # Matches --source-type
path = "exports/friends.zip"    # Relative to the working directory
timezone = "America/New_York"

[sources.journal]
type = "self"
path = "data/journal.ndjson"

[sites.default]
description = "Personal blog"
sources = ["whatsapp_export"]   # Names from [sources.*]

[sites.default.paths]
docs_dir = "docs"
posts_dir = "docs/posts"
media_dir = "docs/posts/media"

[sites.default.output]
adapters = [{ type = "mkdocs", config_path = ".egregora/mkdocs.yml" }]

[sites.retrospective]
description = "Quarterly retro"
sources = ["journal"]

[sites.retrospective.output]
adapters = [{ type = "mkdocs", config_path = ".egregora/mkdocs.retrospective.yml" }]
```

**Selection behavior**

1. CLI `--site`/`--source` or `EGREGORA_SITE`/`EGREGORA_SOURCE` environment variables take precedence.
2. If you omit flags and only one site or source is defined, it is selected automatically.
3. If multiple entries exist and no selection is provided, Egregora picks the `default` site if present, otherwise the first entry and logs a warning. This maintains backward compatibility while encouraging explicit selection.
4. Legacy single-site configs without `[sites.*]` still work. The loader treats them as a single implicit site and applies the provided `--source-type`/`EXPORT_PATH` inputs as before.

**Backward compatibility**

- Existing top-level settings remain valid. When `sites.*` is absent, your file is interpreted as a single-site configuration.
- You can introduce `[sources.*]` gradually; if none are present, CLI positional arguments continue to drive ingestion.
- MkDocs config paths and content directories remain relative to the site root, so you can keep your current layout while adding new sites alongside it.

### Migrating from a single-site config

Follow this checklist to adopt the new structure without disrupting current runs:

1. **Copy your existing `.egregora.toml`** and wrap the content under `[sites.default]` (or another site name of your choice). Keep the nested sections (`[paths]`, `[pipeline]`, `[models]`, etc.) intact—only their prefix changes.
2. **Add a named source** under `[sources.<name>]` that captures the CLI arguments you normally pass (`type`, `path`, `timezone`, date filters). Reference that name from `sites.<name>.sources`.
3. **Keep MkDocs config paths unique** (`sites.<name>.output.adapters[0].config_path`) if you publish more than one site in the same repo. Otherwise you can continue to use `.egregora/mkdocs.yml`.
4. **Test a dry run** with your usual CLI command plus `--site <name>` to confirm the site selection is intentional. Remove the flag once you are comfortable relying on the default-selection rules above.
5. **Clean up legacy keys** once you verify the new layout (optional). The loader will ignore top-level settings when `sites.*` exists, but removing them avoids confusion.

## Advanced Configuration

### Custom Prompt Templates

**MODERN (Phase 2-4)**: Override prompts by placing custom Jinja2 templates in `.egregora/prompts/`.

**Directory structure**:

```
site-root/
├── .egregora.toml
└── .egregora/
    └── prompts/              # Custom prompt overrides (flat directory)
        ├── README.md         # Auto-generated usage guide
        ├── writer.jinja      # Override writer agent prompt
        ├── url_detailed.jinja
        └── media_detailed.jinja
```

**Priority**: Custom prompts (`.egregora/prompts/`) override package defaults (`src/egregora/prompts/`).

**Example**: Override writer prompt

```bash
# Copy default template
mkdir -p .egregora/prompts
cp src/egregora/prompts/writer.jinja .egregora/prompts/writer.jinja

# Edit to customize
vim .egregora/prompts/writer.jinja
```

Agents automatically detect and use custom prompts. Check logs for:
```
INFO:egregora.prompt_templates:Using custom prompts from /path/to/.egregora/prompts
```

### Database Configuration

Egregora stores persistent data in DuckDB:

- **Location**: `.egregora/pipeline.duckdb` (by default)
- **Tables**: `rag_chunks`, `annotations`, `elo_ratings`

To use a different database, modify the `[database]` section in `.egregora.toml`.

### Cache Configuration

Egregora caches LLM responses to reduce API costs:

- **Location**: `.egregora/.cache/` (by default)
- **Type**: Disk-based LRU cache using `diskcache`

To clear the cache:

```bash
rm -rf .egregora/.cache/
```

## Model Selection

### Writer Models

For blog post generation:

- **`google-gla:gemini-flash-latest`**: Fast, creative, excellent for blog posts (recommended)

### Enricher Models

For URL/media descriptions:

- **`google-gla:gemini-flash-latest`**: Fast, cost-effective (recommended)

### Embedding Models

For RAG retrieval:

- **`models/text-embedding-004`**: Latest, 768 dimensions (recommended)
- **`models/text-embedding-003`**: Older, 768 dimensions

## Performance Tuning

### Rate Limiting

Egregora automatically handles rate limits. To customize quotas, edit the `[quota]` section in `.egregora.toml`:

```toml
[quota]
daily_llm_requests = 100
per_second_limit = 0.05  # ~3 requests per minute
concurrency = 1
```

## Examples

### High-Quality Blog

```bash
egregora write export.zip \
  --model=google-gla:gemini-flash-latest \
  --step-size=7 --step-unit=days \
  --enable-enrichment
```

### Fast, Cost-Effective

```bash
egregora write export.zip \
  --model=google-gla:gemini-flash-latest \
  --step-size=7 --step-unit=days \
  --no-enable-enrichment
```

## Next Steps

- [Architecture Overview](../v3/architecture/overview.md) - Understand the pipeline
- [API Reference](../reference/index.md) - Dive into the code
