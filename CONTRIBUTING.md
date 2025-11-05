# Contributing to Egregora

Guide for contributors to Egregora.

## Setup

### Prerequisites

- Python 3.12+
- Git
- Google Gemini API key (for testing)

### Clone and Install

```bash
# Clone repository
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# Quick setup (recommended) - works on Windows, Linux, macOS
python dev_tools/setup_hooks.py

# This will:
# - Sync all dependencies (including lint and test extras)
# - Install pre-commit hooks automatically
# - Set up your development environment

# Alternative: Manual setup
uv sync --extra lint --extra test
uv run pre-commit install
```

### Available Development Commands

All commands work cross-platform (Windows, Linux, macOS):

```bash
python dev_tools/setup_hooks.py   # Set up development environment (deps + pre-commit hooks)
uv run pytest                      # Run tests
uv run pre-commit run --all-files  # Run all linting checks
uv run ruff format .               # Format code
uv run ruff check .                # Check code with ruff
uv run ruff check --fix .          # Lint and auto-fix
```

## TENET-BREAK — Philosophy Violation Flag

Love it. Here’s a single, loud flag tailored for Egregora.

**TENET-BREAK — Philosophy Violation Flag**

Use exactly one tag to mark intentional violations of Egregora’s core principles. It’s a red flare for future cleanup and review.

### When to Use

Only when an external constraint (vendor, deadline, migration window) forces you to go against a tenet such as:

- `no-compat` — No backwards compatibility shims.
- `clean` — Clean code; clarity over cleverness; no “quick-and-dirty.”
- `no-defensive` — Don’t code defensively for “impossible states”; trust types + tests.
- `propagate-errors` — Let errors bubble; don’t swallow or silently recover.

> If you’re not breaking a principle, don’t use TENET-BREAK. Prefer HACK, WORKAROUND, REFACTOR, etc., for normal debt.

### Required Format

```
TENET-BREAK(scope)[owner][priority][due:YYYY-MM-DD]: tenet=<code>; why=<constraint>; exit=<condition>  (#refs)
```

- **scope:** `parser|ingestion|pipeline|rag|embeddings|ranking|ui|api|storage|infra|i18n|compliance`
- **owner:** `@handle` or team
- **priority:** `P0|P1|P2` (default P1)
- **due:** real date to remove/undo the breach
- **tenet:** one of `no-compat|clean|no-defensive|propagate-errors`
- **why:** short factual reason (vendor, rollout, law, bug upstream…)
- **exit:** what must happen so we remove it (partner migrated, lib fixed, feature flag off…)
- **#refs:** link to the issue/PR/spec

### Examples

```python
# TENET-BREAK(api)[@franklin][P0][due:2025-12-01]:
# tenet=no-compat; why=partner still on v1 payloads; exit=partner migrates (#742)
def parse_legacy_payload(...):
    ...
```

```ts
// TENET-BREAK(ui)[@platform][P1][due:2025-11-30]:
// tenet=clean; why=rushed demo; exit=replace with DataGrid v2 (#885)
renderLegacyTable(data)
```

```go
// TENET-BREAK(rag)[@core][P1][due:2025-12-15]:
// tenet=no-defensive; why=uncertain third-party input; exit=type-safe adapter merged (#903)
if q == "" { q = "fallback" } // temporary guard
```

```sql
-- TENET-BREAK(storage)[@data][P1][due:2025-11-20]:
-- tenet=propagate-errors; why=DuckDB UDF lacks error bubbling; exit=upgrade 1.1 (#777)
-- Swallowing NULLs here to keep job alive
```

### Guardrails (Team Discipline)

- Must include owner, due, tenet, why, exit, and a #refs link.
- Default P0 if the breach touches security, privacy, or correctness paths.
- One TENET-BREAK per site (don’t scatter the same rationale everywhere—link to one canonical comment).
- Remove on time: turning a breach into “normal” code is not allowed; either fix or escalate.

### Optional Repo Config (Codify the Tenets)

```yaml
.egregora-tenets.yml

tenets:
  no-compat: "No backwards compatibility layers or shims."
  clean: "Code must be simple, readable, and minimal."
  no-defensive: "Do not guard against impossible states; rely on types/tests."
  propagate-errors: "Do not swallow errors; let them bubble to boundaries."
```

### Cheap CI Lint (Drop-in)

```bash
# required fields present
rg -n 'TENET-BREAK' | rg -v 'tenet=(no-compat|clean|no-defensive|propagate-errors); .*exit=.*due:\d{4}-\d{2}-\d{2}.*#' \
  && echo "TENET-BREAK checks passed" || (echo "TENET-BREAK missing required fields"; exit 1)
```

```python
# Block overdue entries (example, due before today)
python - <<'PY'
import re, sys, datetime, pathlib
today = datetime.date.today()
bad = []
for path in pathlib.Path(".").rglob("*"):
    if path.is_file() and path.suffix not in {".png", ".jpg", ".jpeg", ".pdf", ".bin"}:
        for idx, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if "TENET-BREAK" in line:
                match = re.search(r"due:(\d{4})-(\d{2})-(\d{2})", line)
                if match and datetime.date(*map(int, match.groups())) < today:
                    bad.append(f"{path}:{idx}: overdue TENET-BREAK -> {line.strip()}")
if bad:
    print("\n".join(bad))
    sys.exit(1)
PY
```

### Decision Checklist (Before Adding One)

1. Is this truly a principle breach (not just debt)?
2. Is there a ticket and a real exit?
3. Did you put the breach in the narrowest scope?
4. Did you set a due date you will actually meet?

## Testing

> **Tip:** The RAG retriever depends on DuckDB's `vss` extension. The development install above
> pulls in `duckdb` by default, but the first `pytest` or `egregora process` run still needs to
> download the extension. Ensure your machine has network access or install it manually with
> `duckdb -c "INSTALL vss; LOAD vss"` before running tests.

### Verify Installation

```bash
# Run tests
uv run pytest tests/

# Lint code
uv run ruff check src/

# Format code
uv run ruff format src/

# Type check
uv run mypy src/
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
# Run all pre-commit checks (recommended)
uv run pre-commit run --all-files

# Auto-format code
uv run ruff format .

# Or use individual tools:
# Check linting
uv run ruff check src/

# Auto-fix issues
uv run ruff check --fix src/

# Format code
uv run ruff format src/

# Type check
uv run mypy src/
```

**Note:** Pre-commit hooks will automatically run these checks on `git commit` if you ran `python dev_tools/setup_hooks.py`.

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
    table = parse_export(zip_path)

    assert len(table) > 0
    assert "timestamp" in table.columns
    assert "author" in table.columns

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
