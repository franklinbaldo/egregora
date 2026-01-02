# AI Agent Instructions

> Quick reference for AI agents (Claude, Jules personas) working on Egregora

This document provides practical instructions for AI agents. For comprehensive coding standards and architecture details, see **[CLAUDE.md](CLAUDE.md)**.

---

## 📖 Essential Reading

Before starting work, familiarize yourself with:
- **[CLAUDE.md](CLAUDE.md)**: Authoritative coding standards, architecture patterns, and development practices
- **[.jules/README.md](.jules/README.md)**: Jules persona definitions and scheduling
- **[ARCHITECTURE_CLARIFICATION.md](ARCHITECTURE_CLARIFICATION.md)**: V2/V3 migration details
- **[README.md](README.md)**: User-facing documentation and project overview

---

## 🛠️ Tooling

### Python Environment
- **Always use `uv`** for everything Python-related (environment management, dependency changes, running commands)
- **Never use** `pip`, `pipenv`, or `venv`
- Install/sync dependencies: `uv sync` or `uv sync --all-extras`
- Add/remove packages: `uv add <package>` / `uv remove <package>`
- Run commands: `uv run <tool ...>` (tests, linters, formatters, app entrypoints)

### Local Tooling Over Global
Prefer repository-local tooling over global installs:
```bash
# ✅ Good
uv run ruff check .
uv run pytest tests/

# ❌ Bad
ruff check .  # assumes global install
pytest tests/  # assumes global install
```

---

## 🔄 Development Workflow

### Test-Driven Development (TDD)
- **Default to TDD**: Add or adjust tests alongside any behavior changes or refactors
- Write tests first when implementing new features
- Ensure tests pass before committing: `uv run pytest`

### Commit Practices
- **Small, cohesive commits**: One logical change per commit
- **Descriptive messages**: Follow format in [CLAUDE.md](CLAUDE.md#commit-message-format)
- **Avoid mixing changes**: Don't combine unrelated refactors with fixes/features

### Code Review Checklist (Before Committing)
- [ ] Type annotations present and correct
- [ ] Tests added/updated and passing
- [ ] No banned imports (pandas, pyarrow - use ibis instead)
- [ ] Docstrings for public APIs
- [ ] Error handling uses custom exceptions
- [ ] Pre-commit hooks pass
- [ ] V2/V3 compatibility maintained (see [ARCHITECTURE_CLARIFICATION.md](ARCHITECTURE_CLARIFICATION.md))

---

## ✅ Quality Gates

### Testing
```bash
# Run all tests
uv run pytest

# Run specific tests (narrow scope when appropriate)
uv run pytest tests/unit/
uv run pytest tests/integration/

# Skip slow tests
uv run pytest -m "not slow"

# Run with coverage
uv run pytest --cov=egregora --cov-report=term-missing
```

### Linting & Formatting
```bash
# Check linting
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

### Type Checking
```bash
# Run MyPy on typed code
uv run mypy src/
```

### Documentation
```bash
# Build docs site
uv run mkdocs build

# Serve docs locally
uv run mkdocs serve
```

---

## 📝 Documentation & Examples

- **Runnable snippets**: Ensure all documented commands/code snippets are copy-paste runnable
- **Use `uv run`**: Prefer `uv run ...` invocations in examples
- **Verify examples**: Test usage examples against current code before publishing
- **Update docs**: Keep docs in sync with code changes

---

## 🎨 Frontend/UX (MkDocs/Blog Generation)

### Template Editing
- **Edit source templates**: Modify templates under `src/` (NOT generated `demo/` output)
- **Test changes**: Use `uv run egregora demo` to regenerate demo and inspect changes
- **Validate output**: Check that templates render correctly after changes

### Style Guidelines
- Follow Material for MkDocs conventions
- Ensure accessibility (see [CLAUDE.md](CLAUDE.md) for Palette persona guidelines)
- Test responsive design

---

## 🔒 Security and Dependencies

### Dependency Management
- **Minimal changes**: Keep dependency changes justified and minimal
- **Pinned versions**: Prefer pinned, up-to-date versions through `uv`
- **Security scans**: Run `uv run bandit -r src/` before committing

### Code Security
- **No bypasses**: Avoid `# noqa` or relaxations to bypass linters; fix root causes
- **Validate inputs**: Use Pydantic models for validation (see [CLAUDE.md](CLAUDE.md#pydantic-models-for-validation))
- **Safe queries**: Use Ibis for database operations (parameterized by default)

---

## 🤖 Jules Automation

### Personas
Jules personas are autonomous AI agents that perform maintenance tasks. Active personas include:

| Emoji | Name | Role | Focus |
| :---: | :--- | :--- | :--- |
| 🕸️ | **Weaver** | Integrator | PR Merging & Builds |
| 🧹 | **Janitor** | Hygienist | Code Cleanup, Technical Debt |
| 🔨 | **Artisan** | Craftsman | Code Quality, Refactoring |
| 🎨 | **Palette** | Design Sys | Accessibility & UI |
| 📉 | **Essentialist** | Reducer | Complexity Reduction |

See [.jules/README.md](.jules/README.md) for full persona definitions.

### Scheduler Workflow

The scheduler (`.github/workflows/jules_scheduler.yml`) runs hourly or on dispatch:

```bash
# Manual trigger
uv run --with requests --with python-frontmatter --with jinja2 \
  --with typer --with pydantic \
  python -m jules.cli schedule tick [--all] [--prompt-id <id>] [--dry-run]
```

**How it works**:
1. Scans `.jules/personas/*/prompt.md` for enabled personas
2. Ensures `.jules/personas/<id>/journals/` exists
3. Renders each prompt with injected variables:
   - `{{ emoji }}`: Persona's brand emoji
   - `{{ identity_branding }}`: Standard naming conventions
   - `{{ pre_commit_instructions }}`: Required pre-commit instructions
   - `{{ journal_management }}`: Journal writing instructions
   - `{{ journal_entries }}`: Latest journal entries for context
4. Uses `schedules.toml` or per-prompt metadata to decide when to run
5. Creates sessions via `JulesClient` targeting configured branch

### Auto-fix Workflow

The auto-fix workflow (`.github/workflows/jules-auto-fixer.yml`) triggers after CI failures:

```bash
# Analyze PR and trigger fix
uv run --with requests --with typer --with pydantic \
  python -m jules.cli autofix analyze <pr_number>
```

**How it works**:
1. Triggers after CI completes (only on failure) or via manual dispatch
2. Locates related PR using workflow run payload or head SHA
3. Inspects PR health, summarizes failing checks/logs
4. Pings existing Jules session or creates new one with `JULES_API_KEY`
5. Posts PR comment (via `gh`) describing issues and linking to session

### Persona Configuration

Each `.jules/personas/<name>/prompt.md` supports frontmatter:

```yaml
---
id: agent_id
emoji: 🤖
enabled: true
title: "{{ emoji }} task: description"
schedule: "0 */6 * * *"  # Optional cron expression
---
```

**Journals**: Append-only memory stored in `.jules/personas/<persona>/journals/`
- Format: `YYYY-MM-DD-HHMM-Description.md`
- Included in persona context during scheduling
- Provides continuity across sessions

---

## 🎯 AI Agent Best Practices

### Before Making Changes

1. **Read before modifying**: Always read files before making changes
2. **Search for patterns**: Use grep/glob to find similar code
3. **Check tests**: Look for existing tests to understand behavior
4. **Review exceptions**: Check `exceptions.py` for proper error types
5. **Verify migrations**: Ensure V2/V3 compatibility if needed

### Making Changes

1. **Follow existing patterns**: Match code style and architecture (see [CLAUDE.md](CLAUDE.md))
2. **Use Ibis for data**: Always use Ibis, never pandas directly
3. **Type everything**: Add type annotations to all functions
4. **Handle errors properly**: Use custom exceptions from `exceptions.py`
5. **Test your changes**: Add/update tests for changed behavior

### After Making Changes

1. **Run quality gates**: Tests, linting, type checking
2. **Update documentation**: Keep docs in sync with code
3. **Commit incrementally**: Small, focused commits
4. **Run pre-commit**: `uv run pre-commit run --all-files`

---

## 📚 Key Patterns (Quick Reference)

See [CLAUDE.md](CLAUDE.md#key-patterns) for detailed examples.

### 1. Ibis-First Data Processing
```python
# ✅ Use Ibis for all data operations
def transform(table: ibis.Table) -> ibis.Table:
    return table.filter(ibis._['column'] > value)
```

### 2. Pydantic Models for Validation
```python
from pydantic import BaseModel, field_validator

class Message(BaseModel):
    content: str

    @field_validator('content')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v
```

### 3. Streaming for Large Files
```python
from egregora.database.streaming import stream_whatsapp_zip

for chunk in stream_whatsapp_zip(zip_path):
    process_chunk(chunk)
```

### 4. Custom Exceptions
```python
from egregora.exceptions import EgregoraError

class MyModuleError(EgregoraError):
    """Raised when module-specific error occurs."""
```

---

## 🔄 Updating This File

**When to update**: Introduce new tooling conventions or workflows that others should follow.

**How to update**:
1. Make changes following this document's own guidelines
2. Ensure changes align with [CLAUDE.md](CLAUDE.md)
3. Update last modified date below
4. Commit with descriptive message

---

*Last updated: 2026-01-01*
