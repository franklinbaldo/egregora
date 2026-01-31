# Contributing to Egregora

First off, thank you for considering contributing to Egregora! It's people like you that make Egregora such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## Development Setup

Egregora uses modern Python tooling for a consistent development experience.

### Prerequisites

- **Python 3.12+**: Required for modern type hinting and performance features.
- **[uv](https://github.com/astral-sh/uv)**: Used for dependency management and running tasks.
- **Google Gemini API Key**: Required for AI features (Writer, RAG).

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

4.  **Set environment variables:**
    ```bash
    export GOOGLE_API_KEY="your-api-key"
    ```

## Pull Request Process

1.  **Create a Branch:**
    Use a descriptive branch name: `feature/new-agent`, `fix/db-locking`, `docs/update-readme`.

2.  **Make Changes:**
    Follow the [Code of the Weaver](CLAUDE.md) standards.
    - Write small, atomic commits.
    - Add tests for new features.
    - Ensure type annotations are present.

3.  **Run Tests:**
    Ensure all tests pass before submitting.
    ```bash
    uv run pytest tests/unit/
    ```

4.  **Run Pre-commit:**
    Ensure linting and formatting are correct.
    ```bash
    uv run pre-commit run --all-files
    ```

5.  **Submit PR:**
    - Provide a clear title and description.
    - Reference any related issues.
    - Wait for CI checks to pass.

## Coding Standards

We follow strict coding standards to ensure maintainability and performance. Please read the **[Code of the Weaver (CLAUDE.md)](CLAUDE.md)** for detailed guidelines on:

- **Architecture**: Functional patterns, Ibis-first data processing.
- **Style**: Google-style docstrings, Ruff formatting.
- **Testing**: Pytest fixtures, markers, and coverage.

### Key Rules
- **No Pandas**: Use `ibis-framework` for all data transformations.
- **Type Safety**: Pydantic for validation, strict MyPy checks.
- **Absolute Imports**: No relative imports (e.g., `from . import utils`).

## Testing

We use `pytest` for testing.

- **Unit Tests**: `tests/unit/` - Fast, isolated tests.
- **E2E Tests**: `tests/e2e/` - Full pipeline verification.

```bash
# Run all unit tests
uv run pytest tests/unit/

# Run with coverage
uv run pytest --cov=src/egregora
```

## Documentation

Documentation is built with **MkDocs Material**.

```bash
# Serve docs locally
uv run mkdocs serve
```

Documentation files are located in `docs/`. We use `mkdocstrings` to auto-generate API reference from code docstrings.

## Community

- **Issues**: Use GitHub Issues for bug reports and feature requests.
- **Discussions**: Use GitHub Discussions for questions and ideas.

Thank you for contributing! 🚀
