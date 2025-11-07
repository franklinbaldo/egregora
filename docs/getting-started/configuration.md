# Configuration

Egregora can be configured through CLI arguments, environment variables, and `mkdocs.yml` extras.

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
| `--step-size` | Size of each processing window | `100` |
| `--step-unit` | Unit: `messages`, `hours`, `days` | `messages` |
| `--min-window-size` | Minimum messages per window | `10` |
| `--from-date` | Start date (YYYY-MM-DD) | First message |
| `--to-date` | End date (YYYY-MM-DD) | Last message |

### Model Configuration

| Option | Description | Default |
|--------|-------------|---------|
| `--model` | Gemini model for writing | `models/gemini-2.0-flash-exp` |
| `--enricher-model` | Model for URL/media enrichment | `models/gemini-1.5-flash` |
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

### Required

```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

### Optional

```bash
# Override default model
export EGREGORA_MODEL="models/gemini-2.0-flash-exp"

# Cache directory
export EGREGORA_CACHE_DIR="/path/to/cache"

# Database path
export EGREGORA_DB_PATH="/path/to/egregora.db"
```

## MkDocs Configuration

You can configure Egregora settings in `mkdocs.yml` under the `extra.egregora` key:

```yaml
extra:
  egregora:
    # Model configuration
    models:
      writer: models/gemini-2.0-flash-exp
      enricher: models/gemini-1.5-flash
      embeddings: models/text-embedding-004

    # RAG settings
    rag:
      retrieval_mode: ann
      retrieval_nprobe: 10
      embedding_dimensions: 768

    # Privacy settings
    privacy:
      anonymize: true
      detect_pii: true

    # Feature flags
    features:
      enrich: false
      profile: false
      ranking: false
```

## Advanced Configuration

### Custom Prompt Templates

Egregora uses Jinja2 templates for prompts. You can override them by creating a `templates/` directory:

```bash
my-blog/
├── templates/
│   ├── writer_prompt.jinja2
│   └── enricher_prompt.jinja2
```

See `src/egregora/prompts/` for the default templates.

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

- **`gemini-2.0-flash-exp`**: Fast, creative, excellent for blog posts
- **`gemini-1.5-pro`**: More thoughtful, better for long-form content
- **`gemini-1.5-flash`**: Fastest, good for simple posts

### Enricher Models

For URL/media descriptions:

- **`gemini-1.5-flash`**: Fast, cost-effective (recommended)
- **`gemini-1.5-pro`**: More detailed descriptions

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
  --model=models/gemini-1.5-pro \
  --step-size=7 --step-unit=days \
  --enrich \
  --profile
```

### Fast, Cost-Effective

```bash
egregora process export.zip \
  --model=models/gemini-1.5-flash \
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
