# Quick Start

Get up and running with Egregora in minutes using a sample WhatsApp export.

## Prerequisites

Before starting, make sure you have:
1. Egregora installed (see [Installation](installation.md))
2. An LLM API key configured
3. A WhatsApp export file (or use our sample)

## Running with Sample Data

For this quick start, we'll use a sample WhatsApp export file.

1. **Prepare your data**:
   ```bash
   # Create an input directory
   mkdir -p input/
   
   # Place your WhatsApp export file in the input directory
   # For this example, we'll assume it's named 'whatsapp_chat.txt'
   ```

2. **Run Egregora**:
   ```bash
   # Activate your virtual environment
   source .venv/bin/activate
   
   # Run the egregora command with your input
   egregora --input input/whatsapp_chat.txt --output output/
   ```

3. **Check the results**:
   After processing, you'll find your enriched knowledge graph in the `output/` directory.

## Understanding the Pipeline

Egregora processes your data through several stages:

1. **Input Processing**: Your WhatsApp data is parsed and structured
2. **Privacy Filtering**: Personal information is detected and anonymized
3. **AI Enrichment**: Context, topics, and sentiments are added
4. **Knowledge Graph Generation**: Your data is organized into a searchable format

## Example with Configuration

You can also use a configuration file to customize the processing:

```bash
# Run with a specific configuration file
egregora --config config.yaml --input input/whatsapp_chat.txt --output output/
```

With a config.yaml like:
```yaml
model:
  provider: openai
  name: gpt-4o
privacy:
  enabled: true
enrichment:
  enabled: true
  enrichers:
    - topic
    - sentiment
```

## Next Steps

Now that you've run Egregora with sample data, try:

1. [Configuring](configuration.md) more options specific to your needs
2. Learning about our [Architecture](../guide/architecture.md) to understand the processing pipeline
3. Processing your own data exports
4. Exploring different output formats