# Installation

Get Egregora up and running on your system with these steps.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip
- Access to an LLM API (OpenAI, Anthropic, Ollama, or equivalent)

## Installing uv (if not already installed)

```bash
# Using pip
pip install uv

# Using Homebrew (macOS)
brew install uv

# Using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installing Egregora

```bash
# Clone the repository
git clone https://github.com/your-repo/egregora.git
cd egregora

# Create and activate a virtual environment using uv
uv venv
source .venv/bin/activate

# Install the package in development mode
uv pip install -e .
```

## Setting Up Your LLM Provider

Egregora works with multiple LLM providers. Set your API key in the environment:

```bash
# For OpenAI
export OPENAI_API_KEY="your-api-key"

# For Anthropic
export ANTHROPIC_API_KEY="your-api-key"

# For Ollama (local models)
export OLLAMA_API_BASE="http://localhost:11434"
```

## Configuration

Create a `config.yaml` file in your project root to customize Egregora settings:

```yaml
# config.yaml
model:
  provider: openai  # or anthropic, ollama
  name: gpt-4o  # depends on provider

privacy:
  enabled: true
  anon_threads: 4  # number of threads for anonymization

input:
  source: whatsapp  # or slack, etc.
```

For more details on configuration options, see the [Configuration Guide](configuration.md).