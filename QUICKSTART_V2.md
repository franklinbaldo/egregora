# Egregora v2 Quick Start

## Installation

```bash
# Create virtual environment
uv venv

# Activate it
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e .
```

## Basic Usage

```bash
# Process WhatsApp export
python run_v2.py process \
  --zip_file=whatsapp-export.zip \
  --output=./my-blog \
  --gemini_key=YOUR_GEMINI_API_KEY

# Enable RAG enrichment
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --enable_rag

# Enable profiler
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --enable_profiler

# Debug mode
python run_v2.py process \
  --zip_file=export.zip \
  --output=./blog \
  --gemini_key=YOUR_KEY \
  --debug
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
llm:
  model: models/gemini-2.5-flash
  temperature: 0.7

curator:
  enabled: true
  min_message_length: 15
  max_topics_per_day: 10

enricher:
  enabled: true
  enable_rag: true

writer:
  language: pt-BR
  max_post_length: 5000
```

## Architecture

See `ARCHITECTURE_V2.md` for detailed architecture documentation.

## New Structure

```
src/egregora/
├── core/           # Data models & config
├── agents/         # AI agents (curator, enricher, writer, profiler)
├── tools/          # Pluggable tools (RAG, privacy, etc)
└── pipeline/       # Pipeline orchestrator
```

## Key Features

- **Agent-based**: Each stage is an autonomous LLM agent
- **Pluggable tools**: Easy to add new capabilities
- **Simple pipeline**: Linear, functional flow
- **No event sourcing**: Keep it simple
- **Clean architecture**: Separation of concerns
