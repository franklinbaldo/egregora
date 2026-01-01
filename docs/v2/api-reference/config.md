# Configuration Reference

Egregora uses TOML-based configuration with Pydantic models for type-safe settings management.

## Overview

The configuration system provides:

- **Settings Models**: Pydantic models for all configuration sections
- **Configuration Loading**: Load and validate `.egregora.toml` files
- **Multi-Site Support**: Manage multiple sites from one config file
- **Environment Variables**: Override settings via environment variables
- **Type Safety**: Automatic validation and type checking
- **Defaults**: Sensible defaults for all settings

All configuration is defined in `.egregora.toml` files using TOML format.

## Core Configuration

### EgregoraConfig

Main configuration class that contains all settings.

::: egregora.config.settings.EgregoraConfig
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false
      show_category_heading: true

## Configuration Sections

### Model Settings

LLM model configuration.

::: egregora.config.settings.ModelSettings
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### RAG Settings

Retrieval-Augmented Generation configuration.

::: egregora.config.settings.RAGSettings
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Pipeline Settings

Pipeline execution configuration.

::: egregora.config.settings.PipelineSettings
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Privacy Settings

Privacy and anonymization configuration.

::: egregora.config.settings.PrivacySettings
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

### Site Settings

Site metadata and configuration.

::: egregora.config.settings.SiteSettings
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Configuration Loading

### Loading Functions

::: egregora.config.load_egregora_config
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

::: egregora.config.save_egregora_config
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

::: egregora.config.find_config_file
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3
      members_order: source
      show_if_no_docstring: false

## Utility Functions

### Model Configuration

::: egregora.config.settings.get_google_api_key
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

::: egregora.config.settings.get_model_name
    options:
      show_source: false
      show_root_heading: true
      heading_level: 4
      members_order: source
      show_if_no_docstring: false

## Usage Examples

### Loading Configuration

```python
from egregora.config import load_egregora_config
from pathlib import Path

# Load config from site root
config = load_egregora_config(Path("./my-blog"))

# Access settings
print(config.model.name)  # "gemini-2.5-flash"
print(config.pipeline.window_size)  # 7
print(config.privacy.enabled)  # True
```

### Creating Configuration

```python
from egregora.config.settings import (
    EgregoraConfig,
    ModelSettings,
    PipelineSettings,
    SiteSettings,
)

# Create configuration programmatically
config = EgregoraConfig(
    model=ModelSettings(
        provider="google",
        name="gemini-2.5-flash",
        temperature=0.7,
    ),
    pipeline=PipelineSettings(
        window_size=7,
        window_unit="days",
    ),
    site=SiteSettings(
        name="My Personal Blog",
        author="Alice",
        description="My thoughts and conversations",
    ),
)
```

### Saving Configuration

```python
from egregora.config import save_egregora_config
from pathlib import Path

# Save config to .egregora.toml
save_egregora_config(
    config=config,
    site_root=Path("./my-blog"),
)

# Creates ./my-blog/.egregora.toml
```

### Multi-Site Configuration

```python
from egregora.config import load_egregora_config

# Load specific site from multi-site config
config = load_egregora_config(
    site_root=Path("./multi-blog"),
    site_name="personal",  # Load "personal" site
)

# Config file structure:
# [sites.personal]
# name = "Personal Blog"
# ...
#
# [sites.work]
# name = "Work Blog"
# ...
```

### Environment Variable Overrides

```python
import os
from egregora.config import load_egregora_config

# Set environment variables
os.environ["GOOGLE_API_KEY"] = "your-api-key"
os.environ["EGREGORA_MODEL_NAME"] = "gemini-2.0-flash-exp"

# Load config (environment vars override config file)
config = load_egregora_config(Path("./my-blog"))

# Model name comes from environment variable
print(config.model.name)  # "gemini-2.0-flash-exp"
```

### Accessing Nested Settings

```python
# Model settings
model_name = config.model.name
temperature = config.model.temperature
max_tokens = config.model.max_tokens

# Pipeline settings
window_size = config.pipeline.window_size
window_unit = config.pipeline.window_unit

# RAG settings
top_k = config.rag.top_k
retrieval_mode = config.rag.retrieval_mode

# Privacy settings
enabled = config.privacy.enabled
pii_detection = config.privacy.detect_pii
```

### Model Name Handling

```python
from egregora.config.settings import get_model_name

# Get standardized model name
model = get_model_name("gemini-2.5-flash")
# Returns: "google-gla:gemini-2.5-flash" (Pydantic AI format)

# Alternative formats accepted:
# - "gemini-2.5-flash"
# - "google-gla:gemini-2.5-flash"
# - "models/gemini-2.5-flash"
```

### API Key Management

```python
from egregora.config.settings import get_google_api_key
from egregora.config.exceptions import ApiKeyNotFoundError

try:
    api_key = get_google_api_key()
    print(f"Using API key: {api_key[:10]}...")
except ApiKeyNotFoundError as e:
    print(f"API key not found: {e}")
    # Set GOOGLE_API_KEY environment variable
```

## Configuration File Format

### Basic Configuration

```toml
# .egregora.toml

[site]
name = "My Personal Blog"
author = "Alice"
description = "My thoughts and conversations"
timezone = "America/New_York"

[model]
provider = "google"
name = "gemini-2.5-flash"
temperature = 0.7
max_tokens = 8000

[pipeline]
window_size = 7
window_unit = "days"

[privacy]
enabled = true
detect_pii = true
anonymize_names = false

[rag]
enabled = true
top_k = 10
retrieval_mode = "ann"
```

### Multi-Site Configuration

```toml
# .egregora.toml with multiple sites

[sites.personal]
name = "Personal Blog"
author = "Alice"
description = "Personal thoughts"

[sites.personal.model]
name = "gemini-2.5-flash"
temperature = 0.8

[sites.work]
name = "Work Blog"
author = "Alice (Professional)"
description = "Work-related content"

[sites.work.model]
name = "gemini-2.0-flash-exp"
temperature = 0.5
```

### Advanced Configuration

```toml
[model]
provider = "google"
name = "gemini-2.5-flash"
temperature = 0.7
max_tokens = 8000
top_p = 0.95
top_k = 40

[pipeline]
window_size = 7
window_unit = "days"
overlap_ratio = 0.1
max_windows = 100

[pipeline.enrichment]
enabled = true
max_urls_per_window = 5
max_media_per_window = 10

[pipeline.profiles]
enabled = true
update_interval_days = 7

[pipeline.banners]
enabled = true
batch_size = 5
style = "minimalist"

[rag]
enabled = true
top_k = 10
retrieval_mode = "ann"
embedding_model = "models/gemini-embedding-001"
collection_name = "knowledge_base"

[privacy]
enabled = true
detect_pii = true
anonymize_names = false
pii_threshold = 0.8

[database]
pipeline_db = "duckdb:///.egregora/pipeline.duckdb"
runs_db = "duckdb:///.egregora/runs.duckdb"

[quota]
daily_llm_requests = 100
per_second_limit = 2.0
concurrency = 5
```

## Default Values

| Setting | Default | Description |
|---------|---------|-------------|
| `model.provider` | `"google"` | LLM provider |
| `model.name` | `"gemini-2.5-flash"` | Model name |
| `model.temperature` | `0.7` | Sampling temperature |
| `model.max_tokens` | `8000` | Max output tokens |
| `pipeline.window_size` | `7` | Window size |
| `pipeline.window_unit` | `"days"` | Window unit |
| `rag.enabled` | `true` | Enable RAG |
| `rag.top_k` | `10` | Number of results |
| `privacy.enabled` | `true` | Enable privacy features |
| `quota.daily_llm_requests` | `100` | Daily request limit |
| `quota.per_second_limit` | `2.0` | Requests per second |

See the [Configuration Guide](../getting-started/configuration.md) for the complete auto-generated reference.

## Environment Variables

Configuration can be overridden via environment variables:

| Variable | Setting | Example |
|----------|---------|---------|
| `GOOGLE_API_KEY` | Google API key (required) | `export GOOGLE_API_KEY=your-key` |
| `EGREGORA_MODEL_NAME` | `model.name` | `export EGREGORA_MODEL_NAME=gemini-2.0-flash-exp` |
| `EGREGORA_TEMPERATURE` | `model.temperature` | `export EGREGORA_TEMPERATURE=0.8` |
| `EGREGORA_WINDOW_SIZE` | `pipeline.window_size` | `export EGREGORA_WINDOW_SIZE=14` |

## Validation

Configuration is validated on load:

```python
from egregora.config import load_egregora_config
from egregora.config.exceptions import (
    ConfigValidationError,
    InvalidTimezoneError,
    InvalidRetrievalModeError,
)

try:
    config = load_egregora_config(Path("./my-blog"))
except ConfigValidationError as e:
    # Invalid configuration
    print(f"Validation errors: {e.errors}")
except InvalidTimezoneError as e:
    # Invalid timezone string
    print(f"Invalid timezone: {e.timezone_str}")
except InvalidRetrievalModeError as e:
    # Invalid retrieval mode
    print(f"Invalid mode: {e.mode}")
```

## Type Safety

Pydantic provides automatic type validation:

```python
# Valid configuration
config.model.temperature = 0.8  # OK

# Invalid configuration (raises ValidationError)
try:
    config.model.temperature = "high"  # Type error
except ValidationError as e:
    print(e)

try:
    config.pipeline.window_size = -1  # Value error
except ValidationError as e:
    print(e)
```

## Configuration Updates

Update configuration at runtime:

```python
# Load config
config = load_egregora_config(Path("./my-blog"))

# Update settings
config.model.temperature = 0.9
config.pipeline.window_size = 14

# Save updated config
save_egregora_config(config, Path("./my-blog"))
```

## Migration

The configuration format is versioned and supports migration:

```python
from egregora.config import migrate_config

# Migrate old config to new format
migrated = migrate_config(
    old_config_path=Path("./my-blog/.egregora.old.toml"),
    new_config_path=Path("./my-blog/.egregora.toml"),
)
```

Note: Egregora is in alpha and does not guarantee backward compatibility. Configuration format may change between versions.
