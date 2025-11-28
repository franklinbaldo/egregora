# Installation

Egregora requires Python 3.12+ and uses [uv](https://github.com/astral-sh/uv) for package management.

## Install uv

First, install uv if you haven't already:

=== "macOS/Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows (PowerShell)"

    ```powershell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

## Install Egregora

### From GitHub (Recommended)

Install directly from the repository using uvx:

```bash
uvx --from git+https://github.com/franklinbaldo/egregora egregora --help
```

This will install and run Egregora without any local installation. Use `uvx` for all commands:

```bash
# Initialize a new blog
uvx --from git+https://github.com/franklinbaldo/egregora egregora init my-blog

# Process WhatsApp export
uvx --from git+https://github.com/franklinbaldo/egregora egregora write export.zip
```

### From PyPI

```bash
pip install egregora
```

### From Source

For development (works on Windows, Linux, and macOS):

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Quick setup (installs dependencies + pre-commit hooks)
python dev_tools/setup_hooks.py

# Or manual setup
uv sync --extra lint --extra test
uv run pre-commit install

# Run tests
uv run pytest tests/
```

See [Contributing Guide](../development/contributing.md) for full development setup.

## API Key Setup

Egregora uses Google's Gemini API for content generation. Get a free API key at [https://ai.google.dev/gemini-api/docs/api-key](https://ai.google.dev/gemini-api/docs/api-key).

=== "macOS/Linux"

    ```bash
    export GOOGLE_API_KEY="your-google-gemini-api-key"
    ```

=== "Windows (PowerShell)"

    ```powershell
    $Env:GOOGLE_API_KEY = "your-google-gemini-api-key"
    ```

## Verify Installation

Test that everything is working:

```bash
egregora --version
```

## Optional Dependencies

### Documentation

To build the documentation locally:

```bash
pip install 'egregora[docs]'
mkdocs serve
```

### Linting

For development and code quality:

```bash
pip install 'egregora[lint]'
ruff check src/
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Generate your first blog post
- [Configuration](configuration.md) - Customize your setup
