# AI Agent Instructions

> Quick reference for AI agents (Claude, Jules personas) working on Egregora

This document provides practical instructions for AI agents. For comprehensive coding standards and architecture details, see **[CLAUDE.md](CLAUDE.md)**.

---

## ⭐ Product Philosophy: "Invisible Intelligence, Visible Magic"

**CRITICAL:** Before implementing ANY feature, understand this:

Egregora is NOT a simple chat-to-text converter. Three features make it magical:

1. **🧠 Contextual Memory (RAG)** - Posts reference previous discussions, creating connected narratives
2. **🏆 Content Discovery (Ranking)** - Automatically surfaces best memories
3. **💝 Author Profiles** - Creates loving portraits of people from their messages

**These three features are THE PRODUCT, not optional extras.**

### Implementation Requirements

When implementing or modifying these features:

✅ **MUST be enabled by default** for all users
✅ **MUST work with zero configuration** for 95% of users
✅ **MUST be invisible** to users (they see value, not technology)
✅ **MUST focus on user value** (storytelling, memories, emotional impact)

❌ **DO NOT** make these opt-in or "advanced" features
❌ **DO NOT** require configuration to work
❌ **DO NOT** expose implementation details to users
❌ **DO NOT** deprioritize vs other features

**When in doubt:** These three features are always P0. Everything else supports them.

---

## 📖 Essential Reading

Before starting work, familiarize yourself with:
- **[CLAUDE.md](CLAUDE.md)**: Authoritative coding standards, architecture patterns, and development practices
- **[.team/README.md](.team/README.md)**: Jules persona definitions and scheduling
- **[README.md](README.md)**: User-facing documentation and project overview
- **[docs/user-personas.md](docs/user-personas.md)**: Understand who you're building for (Maya, Tim, Rachel)

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
uv tool run --with mkdocs-material --with mkdocs-blogging-plugin --with mkdocs-macros-plugin --with mkdocs-rss-plugin --with mkdocs-glightbox --with mkdocs-git-revision-date-localized-plugin --with mkdocs-minify-plugin mkdocs serve -f .egregora/mkdocs.yml
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
| 💝 | **Maya** | User Advocate | Non-technical user feedback (on-demand) |

See [.team/README.md](.team/README.md) for full persona definitions.

### Scheduler Workflow

The scheduler (`.github/workflows/jules_scheduler.yml`) runs hourly or on dispatch:

```bash
# Manual trigger
uv run --with requests --with python-frontmatter --with jinja2 \
  --with typer --with pydantic \
  python -m repo.cli schedule tick [--dry-run]
```

**How it works**:
1. Discovers personas from `.team/personas/` (dirs with `prompt.md.j2`)
2. Ensures `.team/personas/<id>/journals/` exists
3. Renders each prompt with injected variables:
   - `{{ emoji }}`: Persona's brand emoji
   - `{{ identity_branding }}`: Standard naming conventions
   - `{{ pre_commit_instructions }}`: Required pre-commit instructions
   - `{{ journal_management }}`: Journal writing instructions
   - `{{ journal_entries }}`: Latest journal entries for context
4. Round-robin selects the next persona alphabetically
5. Creates sessions via `JulesClient` targeting configured branch

### Auto-fix Workflow

The auto-fix workflow (`.github/workflows/jules-auto-fixer.yml`) triggers after CI failures:

```bash
# Analyze PR and trigger fix
uv run --with requests --with typer --with pydantic \
  python -m repo.cli autofix analyze <pr_number>
```

**How it works**:
1. Triggers after CI completes (only on failure) or via manual dispatch
2. Locates related PR using workflow run payload or head SHA
3. Inspects PR health, summarizes failing checks/logs
4. Pings existing Jules session or creates new one with `JULES_API_KEY`
5. Posts PR comment (via `gh`) describing issues and linking to session

### Persona Configuration

Each `.team/personas/<name>/prompt.md` supports frontmatter:

```yaml
---
id: agent_id
emoji: 🤖
enabled: true
title: "{{ emoji }} task: description"
schedule: "0 */6 * * *"  # Optional cron expression
---
```

**Journals**: Append-only memory stored in `.team/personas/<persona>/journals/`
- Format: `YYYY-MM-DD-HHMM-Description.md`
- Included in persona context during scheduling
- Provides continuity across sessions

---

## 🤝 Collaborating with Gemini (for Claude)

When the `gemini` command is available in the environment, Claude can delegate large implementation tasks to Gemini to maximize efficiency and conserve tokens.

### Division of Labor

**Claude's Responsibilities:**
- 🧠 **Strategic thinking** - Architecture decisions and design
- 🔍 **Code analysis** - Understanding existing patterns and identifying gaps
- 📋 **Requirements gathering** - Analyzing user requests and technical context
- 📝 **Specification writing** - Creating detailed implementation plans
- ✅ **Code review** - Validating Gemini's output for quality and correctness
- 🐛 **Debugging** - Complex problem-solving requiring deep reasoning

**Gemini's Responsibilities:**
- ⚙️ **Code generation** - Writing implementations following Claude's specifications
- 🔨 **Boilerplate creation** - Generating repetitive or mechanical code
- 🔄 **Refactoring** - Applying mechanical transformations across files
- 🧪 **Test creation** - Writing test suites following established patterns

### Collaboration Workflow

```bash
# 1. Claude analyzes and creates specification
cat > /tmp/implementation_spec.md << 'EOF'
# TASK: Implement Sprint System for Jules Scheduler

## Context
[Detailed context about current state...]

## Requirements
[What needs to be built...]

## Implementation Details
[Specific files, classes, functions to create/modify...]

## Validation
[How to test the implementation...]
EOF

# 2. Delegate to Gemini
gemini --yolo --prompt "$(cat /tmp/implementation_spec.md)"

# 3. Claude validates output
uv run pytest tests/
uv run ruff check .
```

### Best Practices for Delegation

**✅ Good Candidates for Gemini:**
- Creating 5+ new files with clear patterns
- Implementing CRUD operations from a spec
- Adding comprehensive test coverage
- Refactoring across 10+ files
- Generating configuration files and templates

**❌ Keep with Claude:**
- Architectural design decisions
- Complex debugging and root cause analysis
- Security-critical code review
- Performance optimization requiring analysis
- Resolving ambiguous requirements

### Communication with Gemini

**Effective Specifications Include:**
1. **Context**: What exists now, what's the problem
2. **Objective**: What needs to be built
3. **Files**: Exact paths to create/modify
4. **Code Examples**: Patterns to follow
5. **Validation**: How to test success
6. **Acceptance Criteria**: Checklist of requirements

**Example Prompt Template:**
```markdown
# IMPLEMENTATION: [Feature Name]

## CONTEXT
[Current state, relevant files, architecture]

## OBJECTIVE
[What we're building and why]

## FILES TO CREATE
1. `.team/path/to/new_file.py` - [Purpose]
2. `.team/path/to/config.toml` - [Purpose]

## FILES TO MODIFY
1. `.team/existing.py` - [Add X, modify Y]

## CODE PATTERNS
[Examples of similar code to follow]

## VALIDATION
[Commands to run, expected output]

## ACCEPTANCE CRITERIA
- [ ] Feature X works
- [ ] Tests pass
- [ ] No regressions
```

### Post-Delegation Checklist

After Gemini completes implementation:

- [ ] **Read the changes**: Review all modified files
- [ ] **Run tests**: `uv run pytest`
- [ ] **Check linting**: `uv run ruff check .`
- [ ] **Verify functionality**: Test the feature manually if needed
- [ ] **Review patterns**: Ensure code follows project conventions
- [ ] **Check edge cases**: Identify missing error handling
- [ ] **Update documentation**: Add/update docs as needed

### Token Efficiency

**Why This Matters:**
- Claude's tokens are limited and valuable for analysis
- Gemini is optimized for code generation
- Proper delegation = 10x more work per session

**Metrics:**
- Specification writing: ~5K tokens (Claude)
- Implementation: ~50K tokens (Gemini)
- Review and validation: ~10K tokens (Claude)
- **Total savings**: ~35K tokens by delegating

---

## 🎯 AI Agent Best Practices

### Before Making Changes

1. **Read before modifying**: Always read files before making changes
2. **Search for patterns**: Use grep/glob to find similar code
3. **Check tests**: Look for existing tests to understand behavior
4. **Review exceptions**: Check `exceptions.py` for proper error types
5. **Verify migrations**: Ensure V2/Pure compatibility if needed

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

*Last updated: 2026-01-10*
