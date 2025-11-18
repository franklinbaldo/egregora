# Configuration

Configure Egregora to customize its behavior for your specific needs.

## Configuration File

Egregora can be configured using a YAML file. By default, it looks for `config.yaml` in the current directory, but you can specify a different path with the `--config` option.

## Configuration Options

### Model Settings

Configure the LLM provider and model to use for enrichment:

```yaml
model:
  provider: openai      # Options: openai, anthropic, ollama, groq
  name: gpt-4o          # Model name specific to the provider
  temperature: 0.7      # Creativity parameter (0.0-1.0)
  max_tokens: 4096      # Maximum tokens in response
```

### Privacy Settings

Configure how Egregora handles privacy and anonymization:

```yaml
privacy:
  enabled: true                 # Enable PII detection and anonymization
  anon_threads: 4              # Number of threads for anonymization
  detect_pii: true             # Whether to detect PII
  anonymize_pii: true          # Whether to anonymize detected PII
  pii_types:                   # Types of PII to detect
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - PERSON
    - LOCATION
  anon_prefix: "ANON_"         # Prefix for anonymized entities
```

### Input Settings

Configure how Egregora reads input data:

```yaml
input:
  source: whatsapp            # Options: whatsapp, slack, json
  format: txt                 # Input format
  encoding: utf-8             # Text encoding
  date_format: "%d/%m/%Y"     # Date format in input
```

### Enrichment Settings

Configure what types of enrichment to apply:

```yaml
enrichment:
  enabled: true
  enrichers:
    - topic                  # Topic classification
    - sentiment              # Sentiment analysis
    - entity_recognition     # Named entity recognition
    - summarization          # Content summarization
    - media_analysis         # Analysis of media content
  batch_size: 10             # Number of items to process in each batch
  retry_attempts: 3          # Number of retry attempts for failed enrichments
```

### Output Settings

Configure how Egregora generates output:

```yaml
output:
  format: mkdocs            # Options: mkdocs, hugo, json, markdown
  path: ./output/           # Output directory
  include_media: true       # Whether to include media files
  create_nav: true          # Whether to create navigation structure
```

### Processing Settings

General processing options:

```yaml
processing:
  threads: 4                # Number of threads for parallel processing
  cache_enabled: true       # Enable caching of enrichment results
  cache_path: .cache/       # Path for cache files
  log_level: INFO           # Logging level (DEBUG, INFO, WARNING, ERROR)
```

## Environment Variables

Some settings can also be configured with environment variables:

```bash
# Model provider API settings
OPENAI_API_KEY="your-openai-key"
ANTHROPIC_API_KEY="your-anthropic-key"
OLLAMA_API_BASE="http://localhost:11434"

# General settings
EGREGORA_CONFIG_PATH="./path/to/config.yaml"
EGREGORA_OUTPUT_PATH="./output/"
EGREGORA_LOG_LEVEL="INFO"
```

## Example Configuration

Here's a complete example configuration file:

```yaml
model:
  provider: openai
  name: gpt-4o
  temperature: 0.3
privacy:
  enabled: true
  anon_threads: 4
  pii_types:
    - EMAIL_ADDRESS
    - PHONE_NUMBER
    - PERSON
    - LOCATION
input:
  source: whatsapp
  format: txt
enrichment:
  enabled: true
  enrichers:
    - topic
    - sentiment
    - entity_recognition
output:
  format: mkdocs
  path: ./output/
processing:
  threads: 4
  cache_enabled: true
```