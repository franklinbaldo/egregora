# Configuration

**MODERN (Phase 2-4)**: Egregora configuration lives in `.egregora/config.yml`, separate from rendering (MkDocs).

Configuration sources (priority order):
1. **CLI arguments** - Highest priority (one-time overrides)
2. **`.egregora/config.yml`** - Main configuration file
3. **Defaults** - Defined in Pydantic `EgregoraConfig` model

## CLI Configuration

The `egregora process` command accepts many options:

```bash
egregora process [OPTIONS] EXPORT_PATH
```

### Core Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output` | Output directory for blog | `.` |
| `--timezone` | Timezone for message timestamps | System timezone |
| `--step-size` | Size of each processing window | `1` |
| `--step-unit` | Unit: `messages`, `hours`, `days` | `days` |
| `--min-window-size` | Minimum messages per window | `10` |
| `--from-date` | Start date (YYYY-MM-DD) | First message |
| `--to-date` | End date (YYYY-MM-DD) | Last message |

### Model Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | Gemini model for writing | `models/gemini-flash-latest` |
| `--enricher-model` | Model for URL/media enrichment | `models/gemini-flash-latest` |
| `--embedding-model` | Model for embeddings | `models/text-embedding-004` |

### RAG Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `--retrieval-mode` | `ann` (approximate) or `exact` | `ann` |
| `--retrieval-nprobe` | ANN search quality (1-100) | `10` |
| `--embedding-dimensions` | Embedding dimensions | `768` |

### Privacy Options

| Option | Description | Default |
|--------|-------------|---------|
| `--anonymize/--no-anonymize` | Enable/disable name anonymization | `True` |
| `--detect-pii/--no-detect-pii` | Enable/disable PII detection | `True` |

### Feature Flags

| Option | Description | Default |
|--------|-------------|---------|
| `--enrich/--no-enrich` | Enable URL/media enrichment | `False` |
| `--profile/--no-profile` | Generate author profiles | `False` |

## Environment Variables

**MODERN**: Only credentials live in environment variables (keep out of git).

```bash
export GOOGLE_API_KEY="your-gemini-api-key"  # Required for Gemini API
```

## .egregora/config.yml

**MODERN (Phase 2-4)**: Main configuration file (maps to Pydantic `EgregoraConfig` model).

Generated automatically by `egregora init` or `egregora process` on first run:

```yaml
# Model configuration (pydantic-ai format: provider:model-name)
models:
  writer: google-gla:gemini-flash-latest
  enricher: google-gla:gemini-flash-latest
  enricher_vision: google-gla:gemini-flash-latest
  embedding: google-gla:gemini-embedding-001
  ranking: google-gla:gemini-flash-latest      # Optional
  editor: google-gla:gemini-flash-latest       # Optional

# RAG (Retrieval-Augmented Generation) settings
rag:
  enabled: true
  top_k: 5                    # Number of results to retrieve
  min_similarity_threshold: 0.7         # Minimum similarity threshold (0-1)
  mode: ann                   # "ann" (fast) or "exact" (precise)
  nprobe: 10                  # ANN quality (higher = better, slower)
  embedding_dimensions: 768
  overfetch: null             # Optional overfetch factor

# Writer agent settings
writer:
  custom_instructions: |      # Optional custom prompt additions
    Write in a casual, friendly tone inspired by longform journalism.
  enable_banners: true        # Generate banner images
  max_prompt_tokens: 100000   # Token limit per prompt

# Privacy settings
privacy:
  anonymization_enabled: true
  pii_detection_enabled: true

# Enrichment settings
enrichment:
  enable_url: true
  enable_media: true
  max_enrichments: 50

# Pipeline windowing settings
pipeline:
  step_size: 1                # Size of each window
  step_unit: days             # "messages", "hours", "days", "bytes"
  min_window_size: 10         # Minimum messages per window
  overlap_ratio: 0.2          # Window overlap (0.0-0.5)

# Feature flags
features:
  enable_rag: true
  enable_profiles: false
  enable_ranking: false
```

**Location**: `.egregora/config.yml` in site root (next to `mkdocs.yml`)

## Advanced Configuration

### Custom Prompt Templates

**MODERN (Phase 2-4)**: Override prompts by placing custom Jinja2 templates in `.egregora/prompts/`.

**Directory structure**:

```
site-root/
├── .egregora/
│   ├── config.yml
│   └── prompts/              # Custom prompt overrides
│       ├── README.md         # Auto-generated usage guide
│       ├── system/
│       │   ├── writer.jinja  # Override writer agent prompt
│       │   └── editor.jinja  # Override editor agent prompt
│       └── enrichment/
│           ├── url_simple.jinja
│           ├── url_detailed.jinja
│           ├── media_simple.jinja
│           └── media_detailed.jinja
```

**Priority**: Custom prompts (`.egregora/prompts/`) override package defaults (`src/egregora/prompts/`).

**Example**: Override writer prompt

```bash
# Copy default template
mkdir -p .egregora/prompts/system
cp src/egregora/prompts/system/writer.jinja .egregora/prompts/system/writer.jinja

# Edit to customize
vim .egregora/prompts/system/writer.jinja
```

Agents automatically detect and use custom prompts. Check logs for:
```
INFO:egregora.prompt_templates:Using custom prompts from /path/to/.egregora/prompts
```

### Database Configuration

Egregora stores persistent data in DuckDB:

- **Location**: `.egregora/egregora.db` (by default)
- **Tables**: `rag_chunks`, `annotations`, `elo_ratings`

To use a different database:

```bash
egregora process export.zip --db-path=/custom/path/egregora.db
```

### Cache Configuration

Egregora caches LLM responses to reduce API costs:

- **Location**: `.egregora/cache/` (by default)
- **Type**: Disk-based LRU cache using `diskcache`

To clear the cache:

```bash
rm -rf .egregora/cache/
```

## Model Selection

### Writer Models

For blog post generation:

- **`gemini-flash-latest`**: Fast, creative, excellent for blog posts (recommended)

### Enricher Models

For URL/media descriptions:

- **`gemini-flash-latest`**: Fast, cost-effective (recommended)

### Embedding Models

For RAG retrieval:

- **`text-embedding-004`**: Latest, 768 dimensions (recommended)
- **`text-embedding-003`**: Older, 768 dimensions

## Performance Tuning

### Batch Sizes

Adjust batch sizes in `src/egregora/utils/batch.py` or through configuration:

```yaml
extra:
  egregora:
    batch:
      embedding_batch_size: 100
      enrichment_batch_size: 10
```

### Rate Limiting

Egregora automatically handles rate limits with exponential backoff. To customize:

```python
from egregora.utils.genai import create_gemini_client

client = create_gemini_client(
    api_key="your-key",
    max_retries=5,
    retry_delay=1.0
)
```

## Examples

### High-Quality Blog

```bash
egregora process export.zip \
  --model=models/gemini-flash-latest \
  --step-size=7 --step-unit=days \
  --enrich \
  --profile
```

### Fast, Cost-Effective

```bash
egregora process export.zip \
  --model=models/gemini-flash-latest \
  --step-size=7 --step-unit=days \
  --retrieval-mode=exact \
  --no-enrich
```

### Privacy-Focused

```bash
egregora process export.zip \
  --anonymize \
  --detect-pii \
  --no-enrich
```

## Next Steps

- [Architecture Overview](../guide/architecture.md) - Understand the pipeline
- [Privacy Model](../guide/privacy.md) - Learn about anonymization
- [API Reference](../api/index.md) - Dive into the code
