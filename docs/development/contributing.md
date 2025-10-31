# Contributing to Egregora

Thank you for your interest in contributing to Egregora! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for package management
- Git

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Install with all development dependencies
uv sync --all-extras

# Verify installation
uv run egregora --version
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow these guidelines:

- Write clear, descriptive commit messages
- Add tests for new functionality
- Update documentation as needed
- Follow the existing code style

### 3. Run Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_parser.py

# Run with coverage
uv run pytest --cov=egregora tests/
```

### 4. Lint Your Code

```bash
# Check code style
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/

# Format code
uv run black src/
```

### 5. Update Documentation

If you've added or changed functionality:

```bash
# Update docstrings in your code (mkdocstrings auto-generates API docs)

# Test documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### 6. Submit a Pull Request

1. Push your branch to GitHub
2. Open a pull request against `main`
3. Describe your changes clearly
4. Link any related issues

## Code Style

### Python Style

- **Line length**: 100 characters
- **Formatter**: Black
- **Linter**: Ruff
- **Type hints**: Use throughout
- **Docstrings**: Google style

Example:

```python
def parse_message(text: str, timestamp: datetime) -> ConversationRow:
    """Parse a single WhatsApp message.

    Args:
        text: The message text to parse
        timestamp: When the message was sent

    Returns:
        A ConversationRow with parsed data

    Raises:
        ValueError: If text format is invalid
    """
    ...
```

### Documentation Style

- Use **Google-style docstrings** for all public functions/classes
- Include examples in docstrings when helpful
- Keep user guide documentation concise and practical

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_parser.py           # Unit tests
├── test_integration.py      # Integration tests
└── fixtures/
    ├── vcr_cassettes/       # Recorded API responses
    └── sample_data/         # Test data
```

### Writing Tests

```python
import pytest
from egregora.ingestion import parse_whatsapp_export

def test_parse_basic_message():
    """Test parsing a basic WhatsApp message."""
    # Arrange
    test_file = "tests/fixtures/sample_chat.zip"

    # Act
    df = parse_whatsapp_export(test_file)

    # Assert
    assert len(df) > 0
    assert "author" in df.columns
```

### VCR Tests

For tests involving API calls, use `pytest-vcr`:

```python
@pytest.mark.vcr()
def test_gemini_embedding():
    """Test Gemini embedding with recorded responses."""
    client = create_gemini_client()
    embedding = embed_text("test message", client)
    assert len(embedding) == 768
```

## Project Architecture

### Key Principles

- **Ultra-simple pipeline**: Keep each stage focused
- **Trust the LLM**: Give it context, let it decide
- **Privacy-first**: Anonymize before AI processing
- **DataFrame-based**: Use Ibis for all data transformations

### Adding New Features

When adding new functionality:

1. **Identify the stage**: Which pipeline stage does it belong to?
2. **Update schema**: Modify `core/schema.py` if needed
3. **Add tests**: Cover the happy path and edge cases
4. **Document**: Update docstrings and user guides
5. **Consider privacy**: Ensure no PII leaks

## Common Tasks

### Adding a New CLI Command

```python
# In orchestration/cli.py
@app.command()
def your_command(
    arg1: str = typer.Argument(..., help="Description"),
    opt1: bool = typer.Option(False, help="Description")
) -> None:
    """Brief description of command."""
    # Implementation
```

### Adding a New Pipeline Stage

1. Create module in appropriate directory (e.g., `augmentation/`)
2. Define Ibis transformations
3. Update `orchestration/pipeline.py`
4. Add tests
5. Document in user guide

### Updating Dependencies

```bash
# Add new dependency to pyproject.toml
# Then sync
uv sync

# Lock file is automatically updated
```

## Getting Help

- **Questions**: Open a [GitHub Discussion](https://github.com/franklinbaldo/egregora/discussions)
- **Bugs**: File an [Issue](https://github.com/franklinbaldo/egregora/issues)
- **Security**: Email security concerns privately

## Code of Conduct

Be respectful, inclusive, and constructive. We're all here to make Egregora better!

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
