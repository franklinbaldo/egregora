# Code of the Weaver

> Guidelines for contributors and AI agents working on Egregora

This document serves as the authoritative reference for coding standards, architectural patterns, and development practices in the Egregora project. It is designed to help both human contributors and AI agents (like Claude and Jules) understand the codebase and contribute effectively.

---

## 🎯 Project Overview

**Egregora** transforms your chat history into stories that remember. It doesn't just convert chats to text—it creates connected narratives with contextual memory, automatically discovers your best memories, and generates loving portraits of the people in your conversations.

### What Makes Egregora Special

Three "magical" features work automatically to differentiate Egregora from simple chat-to-text tools:

1. **🧠 Contextual Memory (RAG)**: Posts reference previous discussions, creating connected narratives that feel like a continuing story
2. **🏆 Content Discovery (Ranking)**: Automatically identifies and surfaces your most meaningful conversations
3. **💝 Author Profiles**: Creates emotional portraits of participants—storytelling that captures personality, not statistical analysis

**These three features are THE PRODUCT, not optional extras.** They must be:
- ✅ **Enabled by default** for all users
- ✅ **Zero configuration** for 95% of users
- ✅ **Invisible to users** (they see value, not technology)
- ✅ **The differentiating factor** that makes Egregora magical

### Core Philosophy: "Invisible Intelligence, Visible Magic"

- **Privacy-first**: Runs locally by default, keeping your data private
- **Performance-first**: Uses DuckDB and Ibis for efficient data processing
- **Type-safe AI**: Built with Pydantic-AI for structured, validated outputs
- **Functional patterns**: Data flows through pure functions (`Table -> Table`)
- **Magic by default**: RAG, ranking, and profiling work automatically without configuration

---

## 🏗️ Architecture

### Project Structure

```
src/egregora/
├── orchestration/     # High-level workflows coordinating the pipeline
├── agents/           # AI logic powered by Pydantic-AI
├── database/         # Data persistence using DuckDB and LanceDB
├── input_adapters/   # Logic for reading different data sources
├── output_sinks/  # Logic for writing to different formats
├── transformations/  # Pure data transformation functions
├── rag/             # Vector knowledge base using LanceDB
├── config/          # Configuration management
└── cli/             # Command-line interface using Typer
```

### Key Architectural Patterns

#### 1. **Functional Data Transformations**
All data transformations use Ibis expressions operating on DuckDB tables:
```python
def transform(table: ibis.Table) -> ibis.Table:
    """Pure function transforming data."""
    return table.filter(...).mutate(...)
```

#### 2. **Adapter Pattern**
Input and output adapters implement protocols for extensibility:
- `InputAdapter`: Read from different sources (WhatsApp, Slack, etc.)
- `OutputAdapter`: Write to different formats (MkDocs, SQLite, etc.)

#### 3. **Agent-Based AI**
AI agents are implemented using Pydantic-AI with structured outputs:
- `WriterAgent`: Generates blog posts with contextual memory (uses RAG automatically)
- `ReaderAgent`: Ranks posts using ELO ratings (enables content discovery)
- `ProfileAgent`: Creates emotional portraits of participants (author profiling)
- `BannerAgent`: Creates cover images
- `EnricherAgent`: Analyzes media for context

**⭐ CRITICAL:** The Writer, Reader, and Profile agents implement the three magical features. They must be enabled by default and work without user configuration.

#### 4. **RAG with LanceDB** ⭐ MAGICAL FEATURE
Vector knowledge base for contextual memory (one of the three magical features):
- Stores conversation history as embeddings
- Retrieves related discussions when writing new posts
- Provides depth and continuity to narratives
- **Must be enabled by default** and work transparently
- Users experience: posts that reference "Remember when we discussed..."

---

## 🛠️ Development Setup

### Prerequisites
- Python 3.12+ (specified in `.python-version`)
- [uv](https://github.com/astral-sh/uv) for dependency management
- Google Gemini API key (free tier available)

### Initial Setup

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set up API key
export GOOGLE_API_KEY="your-api-key"
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest --cov=egregora --cov-report=term-missing

# Run specific test markers
uv run pytest -m "not slow"  # Skip slow tests
uv run pytest -m e2e         # Only end-to-end tests
```

### Code Quality Tools

```bash
# Linting with Ruff
uv run ruff check src/ tests/

# Type checking with MyPy
uv run mypy src/

# Dead code detection
uv run vulture src/ tests/

# Security scanning
uv run bandit -r src/
```

---

## 📜 Code Standards

### Style Guide

#### Line Length
- **Ruff**: 110 characters (slightly generous for strings/logs)
- **Black**: 100 characters (formatter)

#### Import Organization
- **Absolute imports only**: No relative imports (enforced by Ruff)
- **Banned imports**:
  - `pandas`: Use `ibis-framework` instead
  - `pyarrow`: Use `ibis-framework` instead

#### Type Annotations
- **Required**: All function signatures must have type annotations
- **MyPy strict mode**: Enabled for most modules
- Exceptions: Some CLI modules (see `pyproject.toml`)

#### Docstrings
- **Style**: Google-style docstrings
- **Required for**: Public classes and complex functions
- **Not required for**: Tests, internal helpers

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/methods**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`

### Error Handling

#### Custom Exceptions
Define domain-specific exceptions in `exceptions.py` modules:
```python
class EgregoraError(Exception):
    """Base exception for all Egregora errors."""

class ConfigurationError(EgregoraError):
    """Raised when configuration is invalid."""
```

#### Exception Hierarchy
- `EgregoraError`: Base for all custom exceptions
- Module-specific bases inherit from `EgregoraError`
- Specific errors inherit from module bases

### Testing Philosophy

#### Test Organization
```
tests/
├── unit/          # Fast, isolated unit tests
├── integration/   # Tests with real dependencies (DB, API)
├── e2e/          # End-to-end pipeline tests
└── fixtures/     # Shared test fixtures
```

#### Test Markers
- `@pytest.mark.slow`: Tests taking >1 second
- `@pytest.mark.e2e`: Full pipeline tests
- `@pytest.mark.benchmark`: Performance baselines

#### Coverage Requirements
- **Current**: 39% (with branch coverage)
- **Target**: Gradually increase with new code
- **Focus**: New code should have high coverage

#### Testing Strategies
- **Property-based testing**: Use Hypothesis for data validation
- **Snapshot testing**: Use Syrupy for Atom XML and templates
- **Mocking**: Use `pytest-mock` and `respx` for HTTP
- **Time travel**: Use `freezegun` for deterministic timestamps

---

## 🤖 AI Agent Guidelines

### General Principles

1. **Read before modifying**: Always read files before making changes
2. **Understand context**: Review related code and documentation
3. **Follow patterns**: Match existing code style and architecture
4. **Test your changes**: Ensure tests pass before committing
5. **Document decisions**: Update relevant docs and add comments where needed

### Jules Personas

This repository uses autonomous AI agents (Jules personas) for maintenance tasks:
- **Weaver**: PR merging and build integration
- **Janitor**: Code cleanup and technical debt
- **Artisan**: Refactoring and code quality
- **Palette**: UI/UX consistency
- **Essentialist**: Complexity reduction

See [.team/README.md](.team/README.md) for persona definitions.

### Collaborating with Gemini

When Gemini is available in the environment (via `gemini` command), you can delegate large implementation tasks to maximize efficiency and conserve your tokens.

**When to Delegate to Gemini:**
- ✅ Large code generation tasks (multiple files, hundreds of lines)
- ✅ Boilerplate implementation following a clear spec
- ✅ Mechanical refactoring across many files
- ✅ Creating test suites following patterns
- ❌ Architecture decisions (you should decide)
- ❌ Code review and analysis (your specialty)
- ❌ Complex debugging (requires deep reasoning)

**How to Delegate:**

1. **Analyze and Plan** (You do this):
   - Read relevant code and understand the context
   - Identify gaps and requirements
   - Create a detailed implementation specification
   - Design the solution architecture

2. **Create Detailed Prompt** (You do this):
   - Write comprehensive instructions in markdown
   - Include code examples and patterns to follow
   - Specify file paths (absolute paths preferred)
   - List acceptance criteria
   - Save to temp file for readability

3. **Delegate Execution** (Gemini does this):
   ```bash
   gemini --yolo --prompt "$(cat /tmp/implementation_spec.md)"
   ```

4. **Monitor and Validate** (You do this):
   - Check Gemini's output
   - Run tests to verify implementation
   - Review code quality
   - Provide feedback or fixes if needed

**Example Workflow:**

```python
# You: Analyze requirements
analysis = """
Current state: blog posts have no tags
Required: Add TagConfig dataclass, tag extraction logic
Files to create: tag_extractor.py
Files to modify: writer_agent.py, blog_models.py
"""

# You: Create detailed spec
spec = create_implementation_spec(analysis)
save_to_file("/tmp/tag_feature_spec.md", spec)

# Gemini: Execute implementation
run_command("gemini --yolo --prompt \"$(cat /tmp/tag_feature_spec.md)\"")

# You: Validate results
run_tests()
review_code_quality()
```

**Benefits:**
- 💰 Conserves your valuable tokens for analysis and planning
- 🚀 Faster execution for mechanical tasks
- 🎯 You focus on architecture and strategy
- 🔍 Gemini handles detailed implementation

**Remember:** You're the architect and code reviewer. Gemini is your implementation assistant. Always validate Gemini's output before committing.

### Working with the Codebase

#### Before Making Changes
1. **Search for patterns**: Use grep/glob to find similar code
2. **Check for tests**: Look for existing tests to understand behavior
3. **Review exceptions**: Check `exceptions.py` for proper error types
4. **Verify migrations**: Ensure V2/Pure compatibility if needed

#### Making Changes
1. **Small commits**: One logical change per commit
2. **Descriptive messages**: Explain why, not just what
3. **Update tests**: Add/modify tests for changed behavior
4. **Run pre-commit**: Let hooks catch issues early

#### Code Review Checklist
- [ ] Type annotations present and correct
- [ ] Tests added/updated
- [ ] No banned imports (pandas, pyarrow)
- [ ] Docstrings for public APIs
- [ ] Error handling with custom exceptions
- [ ] Performance implications considered

---

## 🎯 Key Patterns

### 1. Ibis-First Data Processing

**Always use Ibis** for data operations, never pandas directly:

```python
# ✅ Good
def filter_messages(table: ibis.Table, min_length: int) -> ibis.Table:
    return table.filter(ibis._['message_length'] >= min_length)

# ❌ Bad
def filter_messages(df: pd.DataFrame, min_length: int) -> pd.DataFrame:
    return df[df['message_length'] >= min_length]
```

### 2. Streaming for Large Files

Use streaming for ZIP files and large datasets:

```python
from egregora.database.streaming import stream_whatsapp_zip

# Streaming prevents loading entire file into RAM
for chunk in stream_whatsapp_zip(zip_path):
    process_chunk(chunk)
```

### 3. Pydantic Models for Validation

Use Pydantic for all data models:

```python
from pydantic import BaseModel, Field, field_validator

class Message(BaseModel):
    content: str
    timestamp: datetime
    author: str

    @field_validator('content')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v
```

### 4. Dependency Injection

Use protocols and dependency injection for testability:

```python
from typing import Protocol

class MessageRepository(Protocol):
    def get_messages(self) -> list[Message]: ...

def process_messages(repo: MessageRepository) -> None:
    messages = repo.get_messages()
    # Process messages
```

### 5. Configuration Management

Use Pydantic Settings for configuration:

```python
from pydantic_settings import BaseSettings

class EgregoraConfig(BaseSettings):
    google_api_key: str = Field(alias='GOOGLE_API_KEY')

    class Config:
        env_file = '.env'
```

---

## 🔍 Common Pitfalls

### 1. DuckDB SQL Injection (False Positive)

Ruff rule `S608` is disabled because DuckDB uses parameterized queries through Ibis. This is **safe**:

```python
# Safe - Ibis handles parameterization
table.filter(ibis._['user_input'] == user_value)
```

### 2. Timezone-Naive Datetimes

Rules `DTZ001-DTZ011` are currently ignored but should be addressed gradually. Always use timezone-aware datetimes for new code:

```python
from datetime import datetime, timezone

# ✅ Good
now = datetime.now(tz=timezone.utc)

# ❌ Bad (but currently allowed)
now = datetime.now()
```

### 3. Complexity Limits

Complexity rules (`C901`, `PLR*`) are currently ignored. Keep functions simple, but focus on readability over rigid metrics.

### 4. Test Isolation

Always clean up test resources:

```python
@pytest.fixture
def temp_db():
    db_path = "test.db"
    yield db_path
    # Cleanup
    if Path(db_path).exists():
        Path(db_path).unlink()
```

---

## 📚 Key Documents

- [README.md](README.md): User-facing documentation
- [CHANGELOG.md](CHANGELOG.md): Version history
- [.team/README.md](.team/README.md): AI agent personas
- [docs/](docs/): Full documentation site

---

## 🚀 Contributing

### Workflow

1. **Create a branch**: `git checkout -b feature/your-feature`
2. **Make changes**: Follow the code standards above
3. **Run tests**: `uv run pytest tests/`
4. **Run pre-commit**: `uv run pre-commit run --all-files`
5. **Commit**: Use descriptive commit messages
6. **Push**: `git push origin feature/your-feature`
7. **Open PR**: Describe changes and link issues

### Commit Message Format

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `docs`: Documentation changes
- `chore`: Maintenance tasks

### Pre-commit Hooks

The pre-commit hooks run:
- Ruff linting
- Black formatting
- MyPy type checking
- Pytest (selected tests)

---

## 🎓 Learning Resources

### Ibis
- [Ibis Documentation](https://ibis-project.org/)
- [Ibis Tutorial](https://ibis-project.org/tutorial/intro)

### Pydantic-AI
- [Pydantic-AI Docs](https://ai.pydantic.dev/)
- [Type-safe AI](https://ai.pydantic.dev/why/)

### DuckDB
- [DuckDB Documentation](https://duckdb.org/docs/)
- [Why DuckDB?](https://duckdb.org/why_duckdb)

### Material for MkDocs
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)

---

## 💬 Questions?

- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Security**: See [SECURITY.md](SECURITY.md)

---

*This document is maintained by the Weaver persona and human contributors. Last updated: 2026-01-01*
