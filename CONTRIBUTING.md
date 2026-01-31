# Contributing to Egregora

Thank you for your interest in contributing to Egregora! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12 (see `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management
- Google Gemini API key (for running the pipeline)

### Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/franklinbaldo/egregora.git
    cd egregora
    ```

2.  **Install dependencies:**
    ```bash
    uv sync --all-extras
    ```

3.  **Install pre-commit hooks:**
    ```bash
    uv run pre-commit install
    ```

4.  **Set up your API key:**
    ```bash
    export GOOGLE_API_KEY="your-api-key"
    ```

### Running Tests

```bash
# Run unit tests
uv run pytest tests/unit/ -v

# Run end-to-end tests
uv run pytest tests/e2e/ -v

# Run with coverage
uv run pytest --cov=src/egregora
```

## Contributing Workflow

1.  **Create a branch:**
    ```bash
    git checkout -b feature/your-feature-name
    ```

2.  **Make your changes.** Follow the [Code Standards](#code-standards) below.

3.  **Verify your work:**
    ```bash
    uv run pytest tests/
    uv run pre-commit run --all-files
    ```

4.  **Commit your changes:**
    Use conventional commits (e.g., `feat:`, `fix:`, `docs:`).
    ```bash
    git commit -m "feat: add new adapter for Telegram"
    ```

5.  **Push and open a Pull Request.**

## Code Standards

### Formatting & Linting
We use `ruff` and `black` (via ruff) for formatting.
- Line length: 110 characters
- Imports: Absolute imports only

Run `uv run pre-commit run --all-files` to automatically format your code.

### Type Annotations
- Required for all function signatures.
- MyPy strict mode is enabled.

### Docstrings
- Use Google-style docstrings.
- Required for public classes and complex functions.

## Project Structure

- `src/egregora/`: Main source code.
- `src/egregora/agents/`: Pydantic-AI agents.
- `src/egregora/database/`: DuckDB and persistence.
- `src/egregora/orchestration/`: Pipeline logic.
- `tests/`: Test suite (unit, integration, e2e).

## Questions?

If you have questions, please open an [issue on GitHub](https://github.com/franklinbaldo/egregora/issues).
