# Installation

!!! tip "Just want to get started?"
    If you just want to create your blog, check out our **[Quick Start Guide](quickstart.md)** which covers installation in simple steps.

    This page contains detailed installation instructions for developers and power users.

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

Install the latest version directly from the repository:

```bash
uv tool install git+https://github.com/franklinbaldo/egregora
```

Once installed, you can use the `egregora` command directly:

```bash
# Initialize a new blog
egregora init my-blog

# Process WhatsApp export
egregora write export.zip
```

### From PyPI (Stable)

```bash
uv tool install egregora
```

### From Source

For development (works on Windows, Linux, and macOS):

```bash
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Quick setup (installs dependencies + pre-commit hooks)
python dev_tools/setup_hooks.py

# Or manual setup
uv sync --all-extras
uv run pre-commit install

# Run tests
uv run pytest tests/
```

See [Contributing Guide](https://github.com/franklinbaldo/egregora/blob/main/CONTRIBUTING.md) for full development setup.

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
# Preview your site
uv tool run --from "git+https://github.com/franklinbaldo/egregora[mkdocs]" mkdocs serve -f .egregora/mkdocs.yml
```

## Next Steps

- [Quick Start Guide](quickstart.md) - Generate your first blog post
- [Configuration](configuration.md) - Customize your setup
