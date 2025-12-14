# Configuration API

Configuration management for Egregora, including settings models and validation.

## Overview

Egregora uses **Pydantic V2** for type-safe configuration management. All settings are defined in `.egregora/config.yml` and validated at load time.

## CLI Commands

### Validate Configuration

Check your configuration file for errors:

```bash
egregora config validate
egregora config validate ./my-blog
```

Shows:
- ✅ Validation success with summary
- ❌ Detailed error messages for invalid fields
- ⚠️  Warnings for unusual settings

### Show Configuration

Display current configuration:

```bash
egregora config show
egregora config show ./my-blog
```

## Settings Models

### EgregoraConfig

Root configuration object loaded from `.egregora/config.yml`.

::: egregora.config.settings.EgregoraConfig
    options:
      show_source: false
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 4
      members:
        - models
        - rag
        - writer
        - privacy
        - enrichment
        - pipeline
        - paths
        - database
        - output
        - features
        - quota

### ModelSettings

LLM model configuration for different tasks.

::: egregora.config.settings.ModelSettings
    options:
      show_source: false
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 4

### RAGSettings

RAG (Retrieval-Augmented Generation) configuration.

::: egregora.config.settings.RAGSettings
    options:
      show_source: false
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 4

### PipelineSettings

Pipeline execution settings.

::: egregora.config.settings.PipelineSettings
    options:
      show_source: false
      show_root_heading: true
      show_category_heading: true
      members_order: source
      heading_level: 4

## Configuration Examples

### Minimal Configuration

```yaml
# .egregora/config.yml
models:
  writer: google-gla:gemini-flash-latest

rag:
  enabled: true
  top_k: 5
```

### Full Configuration

```yaml
# .egregora/config.yml

# Model configuration
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  ranking: google-gla:gemini-flash-latest
  editor: google-gla:gemini-flash-latest
  reader: google-gla:gemini-flash-latest
  embedding: models/gemini-embedding-001
  banner: models/gemini-2.5-flash-image

# RAG configuration
rag:
  enabled: true
  top_k: 5
  min_similarity_threshold: 0.7
  indexable_types: ["POST"]
  embedding_max_batch_size: 100
  embedding_timeout: 60.0
  embedding_max_retries: 5

# Writer agent
writer:
  custom_instructions: |
    Write in a casual, friendly tone.
    Focus on practical examples.

# Enrichment
enrichment:
  enabled: true
  enable_url: true
  enable_media: true
  max_enrichments: 50

# Pipeline
pipeline:
  step_size: 1
  step_unit: days                  # "days", "hours", "messages"
  overlap_ratio: 0.2               # 20% overlap
  max_windows: 1                   # Process 1 window (0 = all)
  checkpoint_enabled: false        # Enable incremental processing

# Paths (relative to site root)
paths:
  egregora_dir: .egregora
  rag_dir: .egregora/rag
  lancedb_dir: .egregora/lancedb
  cache_dir: .egregora/cache
  prompts_dir: .egregora/prompts
  docs_dir: docs
  posts_dir: docs/posts
  profiles_dir: docs/profiles
  media_dir: docs/assets/media

# Output format
output:
  format: mkdocs                   # "mkdocs" or "hugo"

# Reader agent
reader:
  enabled: false
  comparisons_per_post: 5
  k_factor: 32
  database_path: .egregora/reader.duckdb

# Quota limits
quota:
  daily_llm_requests: 220
  per_second_limit: 1
  concurrency: 1
```

## Validation

### Field Validators

Configuration fields are validated with custom validators:

```python
# Model name format validation
models:
  writer: google-gla:gemini-flash-latest  # ✅ Valid
  writer: gemini-flash-latest             # ❌ Invalid (missing prefix)

# RAG top_k validation
rag:
  top_k: 5      # ✅ Good
  top_k: 20     # ⚠️  Warning (unusually high)
  top_k: 100    # ❌ Error (exceeds maximum)
```

### Cross-Field Validation

The config validator checks dependencies between fields:

```yaml
# ❌ Error: RAG enabled but lancedb_dir not set
rag:
  enabled: true
paths:
  lancedb_dir: ""  # Empty path

# ⚠️  Warning: Very high token limit
pipeline:
  max_prompt_tokens: 500000  # Exceeds most model limits
```

## Programmatic Usage

### Loading Configuration

```python
from pathlib import Path
from egregora.config.settings import load_egregora_config

# Load from site root
config = load_egregora_config(Path("./my-blog"))

# Access settings
print(config.models.writer)
print(config.rag.enabled)
print(config.pipeline.step_size)
```

### Creating Configuration

```python
from egregora.config.settings import EgregoraConfig, save_egregora_config

# Create with defaults
config = EgregoraConfig()

# Modify settings
config.rag.enabled = False
config.pipeline.step_size = 7

# Save to file
save_egregora_config(config, Path("./my-blog"))
```

### Configuration Overrides

```python
from egregora.config.overrides import ConfigOverrideBuilder

# Build with overrides
overrides = ConfigOverrideBuilder()
overrides.set_model("writer", "google-gla:gemini-pro-latest")
overrides.set_rag_enabled(False)

config = overrides.build(base_config)
```

## See Also

- [Getting Started - Configuration](../getting-started/configuration.md)
- [Privacy Guide](../guide/privacy.md)
- [RAG Configuration](knowledge/rag.md)
