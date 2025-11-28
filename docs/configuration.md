# Configuration Reference

Complete reference for `.egregora/config.yml` configuration file.

**Auto-generated from Pydantic models** - Do not edit manually!
To regenerate: `python dev_tools/generate_config_docs.py`

## Overview

Egregora uses Pydantic V2 for configuration with 13 settings classes:

- [`ModelSettings`](#modelsettings) - LLM model configuration for different tasks.

    - Pydantic-AI agents expect provider-prefixed IDs like ``google-gla:gemini-flash-latest``
    - Direct Google GenAI SDK calls expect ``models/<name>`` identifiers

- [`RAGSettings`](#ragsettings) - Retrieval-Augmented Generation (RAG) configuration.

    Uses LanceDB for vector storage and similarity search.
    Embedding API uses dual-queue router for optimal throughput.

- [`WriterAgentSettings`](#writeragentsettings) - Blog post writer configuration.
- [`PrivacySettings`](#privacysettings) - Privacy and data protection settings (YAML configuration).

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.

    .. warning::
       This Pydantic model (for YAML config) has the same name as the dataclass in
       ``egregora.privacy.config.PrivacySettings`` (for runtime policy). They are NOT
       duplicates - they serve different purposes:

       - **This class**: YAML configuration placeholder (persisted to config.yml)
       - **privacy.config.PrivacySettings**: Runtime policy with tenant isolation, PII
         detection settings, and re-identification escrow (never persisted)

       When privacy configuration becomes user-configurable, this class will hold the
       YAML settings which get mapped to runtime PrivacySettings instances.

- [`EnrichmentSettings`](#enrichmentsettings) - Enrichment settings for URLs and media.
- [`PipelineSettings`](#pipelinesettings) - Pipeline execution settings.
- [`PathsSettings`](#pathssettings) - Site directory paths configuration.

    All paths are relative to site_root (output directory).
    Provides defaults that match the standard .egregora/ structure.

- [`DatabaseSettings`](#databasesettings) - Database configuration for pipeline and observability.

    All values must be valid Ibis connection URIs (e.g. DuckDB, Postgres, SQLite).

- [`OutputSettings`](#outputsettings) - Output format configuration.

    Specifies which output format to use for generated content.

- [`ReaderSettings`](#readersettings) - Reader agent configuration for post evaluation and ranking.
- [`FeaturesSettings`](#featuressettings) - Feature flags for experimental or optional functionality.
- [`QuotaSettings`](#quotasettings) - Configuration for LLM usage budgets and concurrency.

## Root Configuration

The root configuration class is `EgregoraConfig`, which contains all other settings.

### EgregoraConfig

Root configuration for Egregora.

    This model defines the complete .egregora/config.yml schema.

    Example config.yml:
    ```yaml
    models:
      writer: google-gla:gemini-flash-latest
      enricher: google-gla:gemini-flash-latest

    rag:
      enabled: true
      top_k: 5
      min_similarity_threshold: 0.7

    writer:
      custom_instructions: "Write in a casual, friendly tone"
      enable_banners: true

    privacy:
      anonymization_enabled: true
      pii_detection_enabled: true

    pipeline:
      step_size: 1
      step_unit: days

    database:
      pipeline_db: duckdb:///./.egregora/pipeline.duckdb
      runs_db: duckdb:///./.egregora/runs.duckdb

    output:
      format: mkdocs
    ```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `models` | `ModelSettings` | `PydanticUndefined` | LLM model configuration |
| `rag` | `RAGSettings` | `PydanticUndefined` | RAG configuration |
| `writer` | `WriterAgentSettings` | `PydanticUndefined` | Writer configuration |
| `reader` | `ReaderSettings` | `PydanticUndefined` | Reader agent configuration |
| `privacy` | `PrivacySettings` | `PydanticUndefined` | Privacy settings |
| `enrichment` | `EnrichmentSettings` | `PydanticUndefined` | Enrichment settings |
| `pipeline` | `PipelineSettings` | `PydanticUndefined` | Pipeline settings |
| `paths` | `PathsSettings` | `PydanticUndefined` | Site directory paths (relative to site root) |
| `database` | `DatabaseSettings` | `PydanticUndefined` | Database configuration (pipeline and run tracking) |
| `output` | `OutputSettings` | `PydanticUndefined` | Output format settings |
| `features` | `FeaturesSettings` | `PydanticUndefined` | Feature flags |
| `quota` | `QuotaSettings` | `PydanticUndefined` | LLM usage quota tracking |

## Settings Classes

### ModelSettings

LLM model configuration for different tasks.

    - Pydantic-AI agents expect provider-prefixed IDs like ``google-gla:gemini-flash-latest``
    - Direct Google GenAI SDK calls expect ``models/<name>`` identifiers

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `writer` | `str` | `"google-gla:gemini-flash-latest"` | Model for blog post generation (pydantic-ai format) |
| `enricher` | `str` | `"google-gla:gemini-flash-latest"` | Model for URL/text enrichment (pydantic-ai format) |
| `enricher_vision` | `str` | `"google-gla:gemini-flash-latest"` | Model for image/video enrichment (pydantic-ai format) |
| `ranking` | `str` | `"google-gla:gemini-flash-latest"` | Model for post ranking (pydantic-ai format) |
| `editor` | `str` | `"google-gla:gemini-flash-latest"` | Model for interactive post editing (pydantic-ai format) |
| `reader` | `str` | `"google-gla:gemini-flash-latest"` | Model for reader agent (pydantic-ai format) |
| `embedding` | `str` | `"models/gemini-embedding-001"` | Model for vector embeddings (Google GenAI format: models/...) |
| `banner` | `str` | `"models/gemini-2.5-flash-image"` | Model for banner/cover image generation (Google GenAI format) |

### RAGSettings

Retrieval-Augmented Generation (RAG) configuration.

    Uses LanceDB for vector storage and similarity search.
    Embedding API uses dual-queue router for optimal throughput.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable RAG for writer agent |
| `top_k` | `int` | `5` | Number of top results to retrieve |
| `min_similarity_threshold` | `float` | `0.7` | Minimum similarity threshold for results |
| `indexable_types` | `list[str]` | `['POST']` | Document types to index in RAG (e.g., ['POST', 'NOTE']) |
| `embedding_max_batch_size` | `int` | `100` | Maximum texts per batch embedding request (Google API limit: 100) |
| `embedding_timeout` | `float` | `60.0` | HTTP timeout for embedding requests in seconds |
| `embedding_max_retries` | `int` | `5` | Maximum consecutive errors before failing (per endpoint) |

### WriterAgentSettings

Blog post writer configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `custom_instructions` | `str` (optional) | `null` | Custom instructions to guide the writer agent |

### PrivacySettings

Privacy and data protection settings (YAML configuration).

    .. note::
       Currently all privacy features (anonymization, PII detection) are always enabled.
       This config section is reserved for future configurable privacy controls.

    .. warning::
       This Pydantic model (for YAML config) has the same name as the dataclass in
       ``egregora.privacy.config.PrivacySettings`` (for runtime policy). They are NOT
       duplicates - they serve different purposes:

       - **This class**: YAML configuration placeholder (persisted to config.yml)
       - **privacy.config.PrivacySettings**: Runtime policy with tenant isolation, PII
         detection settings, and re-identification escrow (never persisted)

       When privacy configuration becomes user-configurable, this class will hold the
       YAML settings which get mapped to runtime PrivacySettings instances.

| Field | Type | Default | Description |
|-------|------|---------|-------------|

### EnrichmentSettings

Enrichment settings for URLs and media.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `True` | Enable enrichment pipeline |
| `enable_url` | `bool` | `True` | Enrich URLs with LLM-generated descriptions |
| `enable_media` | `bool` | `True` | Enrich images/videos with LLM-generated descriptions |
| `max_enrichments` | `int` | `50` | Maximum number of enrichments per run |

### PipelineSettings

Pipeline execution settings.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `step_size` | `int` | `1` | Size of each processing window (number of messages, hours, days, etc.) |
| `step_unit` | `WindowUnit` | `"WindowUnit.DAYS"` | Unit for windowing: 'messages' (count), 'hours'/'days' (time), 'bytes' (max packing) |
| `overlap_ratio` | `float` | `0.2` | Fraction of window to overlap for context continuity (0.0-0.5, default 0.2 = 20%) |
| `max_window_time` | `int` (optional) | `null` | Maximum time span per window in hours (optional constraint) |
| `timezone` | `str` (optional) | `null` | Timezone for timestamp parsing (e.g., 'America/New_York') |
| `batch_threshold` | `int` | `10` | Minimum items before batching API calls |
| `from_date` | `str` (optional) | `null` | Start date for filtering (ISO format: YYYY-MM-DD) |
| `to_date` | `str` (optional) | `null` | End date for filtering (ISO format: YYYY-MM-DD) |
| `max_prompt_tokens` | `int` | `100000` | Maximum tokens per prompt (default 100k, even if model supports more). Prevents context overflow and controls costs. |
| `use_full_context_window` | `bool` | `False` | Use full model context window (overrides max_prompt_tokens cap) |
| `max_windows` | `int` (optional) | `1` | Maximum windows to process per run (1=single window, 0=all windows, None=all) |
| `checkpoint_enabled` | `bool` | `False` | Enable incremental processing with checkpoints (opt-in). Default: always rebuild from scratch for simplicity. |

### PathsSettings

Site directory paths configuration.

    All paths are relative to site_root (output directory).
    Provides defaults that match the standard .egregora/ structure.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `egregora_dir` | `str` | `".egregora"` | Egregora internal directory (contains config, rag, cache) |
| `rag_dir` | `str` | `".egregora/rag"` | RAG database and embeddings storage (DuckDB backend) |
| `lancedb_dir` | `str` | `".egregora/lancedb"` | LanceDB vector database directory (LanceDB backend) |
| `cache_dir` | `str` | `".egregora/.cache"` | API response cache |
| `prompts_dir` | `str` | `".egregora/prompts"` | Custom prompt overrides |
| `docs_dir` | `str` | `"docs"` | Documentation/content directory |
| `posts_dir` | `str` | `"posts"` | Blog posts directory |
| `profiles_dir` | `str` | `"profiles"` | Author profiles directory |
| `media_dir` | `str` | `"media"` | Media files (images, videos) directory |
| `journal_dir` | `str` | `"journal"` | Agent execution journals directory |

### DatabaseSettings

Database configuration for pipeline and observability.

    All values must be valid Ibis connection URIs (e.g. DuckDB, Postgres, SQLite).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pipeline_db` | `str` | `"duckdb:///./.egregora/pipeline.duckdb"` | Pipeline database connection URI (e.g. 'duckdb:///absolute/path.duckdb', 'duckdb:///./.egregora/pipeline.duckdb' for a site-relative file, or 'postgres://user:pass@host:5432/dbname'). |
| `runs_db` | `str` | `"duckdb:///./.egregora/runs.duckdb"` | Run tracking database connection URI (e.g. 'duckdb:///absolute/runs.duckdb', 'duckdb:///./.egregora/runs.duckdb' for a site-relative file, or 'postgres://user:pass@host:5432/dbname'). |

### OutputSettings

Output format configuration.

    Specifies which output format to use for generated content.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `Literal` | `"mkdocs"` | Output format: 'mkdocs' (default), 'hugo', or future formats (database, s3) |
| `mkdocs_config_path` | `str` (optional) | `null` | Path to mkdocs.yml config file, relative to site root. If None, defaults to '.egregora/mkdocs.yml' |

### ReaderSettings

Reader agent configuration for post evaluation and ranking.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `False` | Enable reader agent for post quality evaluation |
| `comparisons_per_post` | `int` | `5` | Number of pairwise comparisons per post for ELO ranking |
| `k_factor` | `int` | `32` | ELO K-factor controlling rating volatility (16=stable, 64=volatile) |
| `database_path` | `str` | `".egregora/reader.duckdb"` | Path to reader database for ELO ratings and comparison history |

### FeaturesSettings

Feature flags for experimental or optional functionality.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ranking_enabled` | `bool` | `False` | Enable Elo-based post ranking (deprecated: use reader.enabled instead) |
| `annotations_enabled` | `bool` | `True` | Enable conversation annotations/threading |

### QuotaSettings

Configuration for LLM usage budgets and concurrency.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `daily_llm_requests` | `int` | `220` | Soft limit for daily LLM calls (writer + enrichment). |
| `per_second_limit` | `int` | `1` | Maximum number of LLM calls allowed per second (for async guard). |
| `concurrency` | `int` | `1` | Maximum number of simultaneous LLM tasks (enrichment, writing, etc). |

## Example Configuration

```yaml
# Minimal configuration
models:
  writer: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001

rag:
  enabled: true
  top_k: 5

pipeline:
  step_size: 1
  step_unit: days
```

```yaml
# Complete configuration with all options
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  ranking: google-gla:gemini-flash-latest
  editor: google-gla:gemini-flash-latest
  reader: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  banner: google-gla:gemini-imagen-latest

rag:
  enabled: true
  top_k: 5
  min_similarity_threshold: 0.7
  indexable_types: ["POST"]
  embedding_max_batch_size: 100
  embedding_timeout: 60.0
  embedding_max_retries: 3

writer:
  custom_instructions: |
    Write in a conversational tone.
    Focus on clarity and simplicity.

enrichment:
  enabled: true
  enable_url: true
  enable_media: true
  max_enrichments: 100

pipeline:
  step_size: 1
  step_unit: days
  overlap_ratio: 0.0
  timezone: UTC
  checkpoint_enabled: false

paths:
  egregora_dir: .egregora
  docs_dir: docs
  posts_dir: docs/posts

database:
  pipeline_db: .egregora/pipeline.duckdb
  runs_db: .egregora/runs.duckdb

output:
  format: mkdocs

reader:
  enabled: true
  comparisons_per_post: 5
  k_factor: 32

quota:
  daily_llm_requests: null
  per_second_limit: 1.0
  concurrency: 5
```

## Custom Prompts

Override default prompts by placing Jinja2 templates in `.egregora/prompts/`:

- `writer.jinja` - Writer agent prompt
- `banner.jinja` - Banner agent prompt
- `reader_system.jinja` - Reader system prompt
- `media_detailed.jinja` - Media enrichment prompt
- `url_detailed.jinja` - URL enrichment prompt

## Programmatic Configuration

```python
from egregora.config.overrides import ConfigOverrideBuilder
from egregora.config.settings import EgregoraConfig

# Load base config
config = EgregoraConfig.load()

# Build overrides
overrides = ConfigOverrideBuilder()
overrides.set_model("writer", "google-gla:gemini-pro-latest")
overrides.set_rag_enabled(False)

# Apply overrides
config = overrides.build(config)
```

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Quick reference
- [Architecture Overview](architecture/README.md) - System architecture
- [Protocols](architecture/protocols.md) - Core protocols
