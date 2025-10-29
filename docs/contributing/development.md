# Development Guide

Guide for contributors to Egregora.

## Setup

### Prerequisites

- Python 3.11+
- Git
- Google Gemini API key (for testing)

### Clone and Install

```bash
# Clone repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e '.[docs,lint,test]'
```

> **Tip:** The RAG retriever depends on DuckDB's `vss` extension. The development install above
> pulls in `duckdb` by default, but the first `pytest` or `egregora process` run still needs to
> download the extension. Ensure your machine has network access or install it manually with
> `duckdb -c "INSTALL vss; LOAD vss"` before running tests.

### Verify Installation

```bash
# Run tests
pytest tests/

# Lint code
ruff check src/
black --check src/

# Type check
mypy src/
```

## Project Structure

```
egregora/
├── src/egregora/        # Main source code
│   ├── parser.py        # WhatsApp parsing
│   ├── anonymizer.py    # Privacy layer
│   ├── enricher.py      # Enrichment
│   ├── writer.py        # LLM post generation
│   ├── pipeline.py      # Orchestrator
│   ├── cli.py           # CLI interface
│   ├── rag/             # RAG system
│   └── ranking/         # ELO ranking
├── tests/               # Test suite
├── docs/                # Documentation
├── examples/            # Usage examples
├── pyproject.toml       # Project config
└── README.md            # Main readme
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
```

### 2. Make Changes

Edit code in `src/egregora/`.

### 3. Write Tests

Add tests in `tests/`:

```python
# tests/test_my_feature.py
def test_my_feature():
    result = my_function("input")
    assert result == "expected"
```

### 4. Run Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_parser.py

# Run with coverage
pytest --cov=egregora tests/
```

### 5. Lint and Format

```bash
# Check linting
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
black src/

# Type check
mypy src/
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add my feature"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `refactor:` - Code refactoring
- `test:` - Tests
- `chore:` - Maintenance

### 7. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

## Code Style

### Formatting

- **Line length:** 100 characters
- **Formatter:** Black
- **Linter:** Ruff
- **Type hints:** Required for public APIs

### Conventions

```python
# Good
from ibis.expr.types import Table


def parse_export(zip_path: Path) -> Table:
    """Parse WhatsApp export into an Ibis table.

    Args:
        zip_path: Path to ZIP file

    Returns:
        Table with [timestamp, author, message, media, media_metadata]
    """
    ...

# Docstring format: Google style
# Type hints: Always for function signatures
# Variable names: snake_case
# Constants: UPPER_CASE
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/

# With verbose output
pytest -v tests/

# Specific test
pytest tests/test_parser.py::test_parse_basic

# With coverage report
pytest --cov=egregora --cov-report=html tests/
```

### Writing Tests

```python
import pytest
from pathlib import Path
from egregora.parser import parse_export

def test_parse_export_basic():
    """Test basic export parsing."""
    zip_path = Path("tests/fixtures/sample-export.zip")
    df = parse_export(zip_path)

    assert len(df) > 0
    assert "timestamp" in df.columns
    assert "author" in df.columns

def test_parse_export_invalid_file():
    """Test parsing invalid file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_export(Path("nonexistent.zip"))
```

### Test Fixtures

Place test data in `tests/fixtures/`:

```
tests/
├── fixtures/
│   ├── sample-export.zip
│   ├── sample-messages.txt
│   └── expected-output.md
└── test_parser.py
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """One-line summary.

    Longer description if needed.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When input is invalid

    Example:
        >>> my_function("test", 42)
        True
    """
    ...
```

### Documentation Files

Documentation is in `docs/`:

```
docs/
├── README.md              # Documentation index
├── getting-started/       # User guides
├── features/              # Feature docs
├── guides/                # How-to guides
├── reference/             # API/CLI reference
└── contributing/          # This file
```

Update docs when adding features.

## Architecture

### Key Design Principles

1. **Trust the LLM** - Let it make editorial decisions
2. **Ibis tables all the way** - Stay in DuckDB, convert to pandas only at boundaries
3. **Privacy first** - Anonymize before LLM sees data
4. **Simple pipeline** - No complex agents or events
5. **Functional style** - Pure functions where possible

### Adding Features

**Before adding complexity, ask:**
1. Can the LLM do this with better prompting?
2. Is this truly necessary or nice-to-have?
3. Can we solve this with existing tools?

**If adding a new component:**
1. Keep it simple
2. Add tests
3. Document it
4. Update architecture docs

## Common Tasks

### Add New CLI Command

1. Edit `src/egregora/cli.py`
2. Add Typer command:

```python
@app.command()
def my_command(
    arg: Annotated[str, typer.Argument(help="Description")]
):
    """Command description."""
    # Implementation
```

3. Update `docs/reference/cli.md`

### Add New Parser Format

1. Edit `src/egregora/parser.py`
2. Add date format pattern
3. Add tests in `tests/test_parser.py`

### Improve Anonymization

1. Edit `src/egregora/anonymizer.py`
2. Add tests in `tests/test_anonymization.py`
3. Update `docs/features/anonymization.md`

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or use `--debug` flag in CLI.

### Inspect Tables

```python
import ibis

table = parse_export(zip_path)
print(table.schema())
print(table.limit(5).execute())  # pandas DataFrame for quick inspection
```

### Profile Performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = my_function()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)
```

## Release Process

(For maintainers)

1. **Update version** in `pyproject.toml`
2. **Update CHANGELOG.md**
3. **Run full test suite**
4. **Build package:** `python -m build`
5. **Publish to PyPI:** `twine upload dist/*`
6. **Tag release:** `git tag v0.2.0 && git push --tags`
7. **Create GitHub release** with changelog

## Getting Help

- **Questions:** Open a Discussion on GitHub
- **Bugs:** Open an Issue with reproduction steps
- **Features:** Open an Issue describing the use case

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to build great software.

## License

Egregora is MIT licensed. See LICENSE file.
