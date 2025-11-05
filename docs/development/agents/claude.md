# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git Workflow - CRITICAL

**⚠️ NEVER commit directly to main branch. ALWAYS use feature branches and pull requests.**

### Standard Workflow for New Features

```bash
# 1. Create feature branch from main
git checkout main
git pull origin main
git checkout -b feature/descriptive-name

# 2. Make changes and commit
git add .
git commit -m "Your commit message"

# 3. Push feature branch
git push origin feature/descriptive-name

# 4. Create pull request using gh CLI
gh pr create --title "Feature: Description" --body "Details..."

# 5. After PR is merged, delete local branch
git checkout main
git pull origin main
git branch -d feature/descriptive-name
```

### When to Create Feature Branches

**ALWAYS create a feature branch for:**
- ✅ New features (e.g., banner generation, new tools)
- ✅ Bug fixes
- ✅ Refactoring
- ✅ Documentation updates
- ✅ Configuration changes
- ✅ ANY code changes that will be committed

**The ONLY exception:**
- Emergency hotfixes explicitly requested by the user with "push directly to main"

### Branch Naming Convention

- `feature/` - New features (e.g., `feature/banner-generation`)
- `fix/` - Bug fixes (e.g., `fix/date-parsing-error`)
- `refactor/` - Code refactoring (e.g., `refactor/extract-handlers`)
- `docs/` - Documentation only (e.g., `docs/add-architecture-guide`)
- `test/` - Test additions/fixes (e.g., `test/add-banner-tests`)

## Development Commands

### Setup (Cross-Platform)

**Quick setup** - works on Windows, Linux, and macOS:
```bash
# Clone and install dependencies
git clone https://github.com/franklinbaldo/egregora.git
cd egregora

# One-command setup (installs dependencies + pre-commit hooks)
python dev_tools/setup_hooks.py

# Or manual setup
uv sync --extra lint --extra test
uv run pre-commit install
```

The setup script will:
- Install all dependencies (including lint and test extras)
- Install pre-commit hooks automatically
- Configure your development environment

Pre-commit hooks will run automatically on `git commit` to ensure code quality.

### Testing
```bash
# Run all tests
uv run pytest tests/

# Run specific test suites
uv run pytest tests/test_gemini_dispatcher.py  # Dispatcher tests
uv run pytest tests/test_with_golden_fixtures.py  # VCR integration tests

# Lint code
uv run ruff check src/
uv run ruff format src/ --check

# Run all pre-commit checks manually
uv run pre-commit run --all-files
```

### Running Egregora Locally
```bash
# Set API key
export GOOGLE_API_KEY="your-key"

# Process WhatsApp export
uv run egregora process /path/to/export.zip --output ./output

# Initialize new site
uv run egregora init my-blog

# Run editor on existing post
uv run egregora edit posts/2025-01-15-post.md

# Serve generated site locally
cd output && uvx --with mkdocs-material --with mkdocs-blogging-plugin mkdocs serve
```

### Key Project Configurations
- **Python**: 3.12+ required
- **Package manager**: uv (modern Python package management)
- **Linting**: ruff (replaces black + isort)
- **Type checking**: mypy (strict mode with per-file overrides)
- **Line length**: 100 characters
- **CLI entry point**: `egregora.orchestration.cli:main`
- **Testing**: pytest with VCR cassettes for API replay

## Ibis-First Coding Standard

**Policy: All DataFrame operations in `src/egregora/` must use Ibis + DuckDB. Pandas imports are banned.**

### Why Ibis-First?

1. **Memory efficiency**: Stream large datasets without full materialization
2. **Unified API**: Single interface for DuckDB, no pandas/PyArrow switching
3. **Correct timezone handling**: Avoids PyArrow timezone conversion bugs
4. **Simpler dependencies**: One data layer instead of three (Ibis, pandas, PyArrow)
5. **Better performance**: DuckDB's native execution is faster than pandas for most operations

### Streaming Utilities

Use `egregora.data` module for all data operations:

```python
from egregora.streaming import stream_ibis, ensure_deterministic_order

# Stream large tables efficiently
ordered_table = ensure_deterministic_order(table)
for batch in stream_ibis(ordered_table, con, batch_size=1000):
    for row in batch:
        process(row)
```

Available utilities:
- `stream_ibis(expr, con, batch_size)`: Stream Ibis expression in batches
- `ensure_deterministic_order(expr)`: Sort by canonical keys (published_at, id)
- `copy_expr_to_parquet(expr, con, path)`: Write directly to Parquet
- `copy_expr_to_ndjson(expr, con, path)`: Write directly to NDJSON

### Enforcement

**CI checks:**
- Pre-commit hook scans for `import pandas` in `src/egregora/`
- `tests/test_banned_imports.py` uses AST to enforce the ban
- Allowed exceptions: `src/egregora/compat/`, `src/egregora/testing/`

**If you need pandas for a legitimate reason:**
1. Check if Ibis can do it (it usually can)
2. Use `egregora.data.stream` utilities instead
3. If truly necessary, place code in `src/egregora/compat/` and document why

### Examples

**❌ Don't do this:**
```python
df = table.to_pandas()  # Materializes full table
for row in df.iterrows():
    process(row)
```

**✅ Do this instead:**
```python
from egregora.streaming import stream_ibis

for batch in stream_ibis(table, con, batch_size=1000):
    for row in batch:
        process(row)
```

**❌ Don't do this:**
```python
arrow_table = table.to_pyarrow()
rows = arrow_table.to_pylist()  # Fails with timezone-aware timestamps
```

**✅ Do this instead:**
```python
from egregora.streaming import ensure_deterministic_order, stream_ibis

ordered = ensure_deterministic_order(table)
all_rows = []
for batch in stream_ibis(ordered, con):
    all_rows.extend(batch)
```

## Architecture Overview

### Design Philosophy
**"Trust the LLM"** - Give AI complete context and let it make editorial decisions (how many posts, what to write). Use tool calling for structured output. Keep the pipeline simple and composable.

### Core Design Principles
1. **Staged Pipeline Architecture** (not ETL) - Distinct phases with clear responsibilities
2. **Privacy-First** - Real names converted to deterministic UUIDs before any LLM interaction
3. **Stateful Knowledge** - RAG indexes posts for context-aware writing
4. **DataFrame-Based** - Ibis + DuckDB for transformations and vector search
5. **LLM-Driven Content** - AI decides what's worth writing, how many posts per period, all metadata

### Pipeline Stages (6 Stages)

```
Ingestion → Privacy → Augmentation → Knowledge → Generation → Publication
```

1. **Ingestion** (`src/egregora/ingestion/`)
   - `parser.py`: Parse WhatsApp ZIP to Ibis tables (CONVERSATION_SCHEMA)
   - Extracts: messages, timestamps, authors, media references
   - Detects `/egregora` commands (opt-out, set alias, set bio)

2. **Privacy** (`src/egregora/privacy/`)
   - `anonymizer.py`: Convert names → deterministic UUIDs
   - `detector.py`: Scan for PII (phone, email, addresses)
   - Opt-out management from WhatsApp commands

3. **Augmentation** (`src/egregora/augmentation/`)
   - `enrichment/core.py`: LLM descriptions for URLs/media
   - `enrichment/batch.py`: Batch processing with GeminiBatchClient
   - `profiler.py`: Generate author bios from conversations
   - Uses `EnrichmentCache` (diskcache) to avoid re-enriching

4. **Knowledge** (`src/egregora/knowledge/`)
   - `rag/`: Vector store (RAG_CHUNKS_SCHEMA in DuckDB)
     - `embedder.py`: Generate embeddings with Gemini
     - `store.py`: DuckDB VSS extension for ANN search
     - `retriever.py`: Retrieve similar past posts/media
     - `chunker.py`: Split documents for indexing
   - `annotations.py`: Conversation metadata, threading
   - `ranking/`: Elo-based content quality scoring
     - `elo.py`: Elo rating calculations
     - `agent.py`: LLM judges post quality
     - `store.py`: Persist ratings in DuckDB

5. **Generation** (`src/egregora/generation/`)
   - `writer/core.py`: LLM generates 0-N posts per period with tool calling
   - `writer/context.py`: Assemble RAG context for writer
   - `writer/tools.py`: Pydantic models for structured output
   - `editor/agent.py`: Interactive AI-powered post refinement
   - `editor/document.py`: Document state management for editing

6. **Initialization** (`src/egregora/init/`)
   - `scaffolding.py`: MkDocs project initialization
   - Templates in `src/egregora/templates/` (Jinja2)

### Core Infrastructure

- **Database Schemas** (`src/egregora/core/database_schema.py`)
  - All table schemas defined with Ibis for type safety
  - **Ephemeral schemas**: CONVERSATION_SCHEMA (in-memory, never persisted)
  - **Persistent schemas**: RAG_CHUNKS_SCHEMA, ELO_RATINGS_SCHEMA, ANNOTATIONS_SCHEMA

- **Configuration** (`src/egregora/config/`)
  - `site.py`: Load egregora config from mkdocs.yml
  - `model.py`: Model names, retrieval settings
  - Settings loaded from `extra.egregora` in mkdocs.yml

- **Orchestration** (`src/egregora/orchestration/`)
  - `cli.py`: Typer-based CLI (commands: init, process, edit, parse, group, etc.)
  - `pipeline.py`: Main pipeline orchestration
  - `write_post.py`: Per-period post generation
  - `database.py`: DuckDB connection management
  - `checkpoints.py`: Save/restore pipeline state

- **Utils** (`src/egregora/utils/`)
  - `gemini_dispatcher.py`: Retry logic, error handling for Gemini API
  - `batch.py`: GeminiBatchClient for batch API requests
  - `cache.py`: EnrichmentCache (diskcache wrapper)
  - `genai.py`: Gemini client initialization

- **Testing** (`src/egregora/testing/`)
  - `gemini_recorder.py`: Record/replay Gemini API calls for VCR tests

### Data Flow Example

```
WhatsApp export.zip
  ↓ [Ingestion] parser.py
Ibis Table (CONVERSATION_SCHEMA)
  ↓ [Privacy] anonymizer.py
Anonymized Table (author = UUID)
  ↓ [Augmentation] enrichment + profiler
Enriched Table + Author Profiles
  ↓ group_by_period() in pipeline.py
Dict[period_key, Table]
  ↓ [Knowledge] RAG retrieval + annotations
Context for each period
  ↓ [Generation] writer with tool calling
Posts (.md with frontmatter)
  ↓ [Publication] MkDocs templates
Static site (mkdocs serve)
```

### Important Invariants

1. **Real names never reach LLM** - Anonymization happens in privacy stage before any LLM calls
2. **UUIDs are deterministic** - Same author always gets same UUID (stable across runs)
3. **Schemas enforce contracts** - All data transformations validated by Ibis schemas
4. **RAG is stateful** - Vector store persists across runs for context continuity
5. **VCR tests use exact mode** - `retrieval_mode="exact"` avoids VSS extension dependency in tests
6. **CONVERSATION_SCHEMA is canonical** - All pipeline stages must return tables conforming to `CONVERSATION_SCHEMA` from `core/database_schema.py`. Stages that add columns during processing MUST filter them out before returning (see `augmentation/enrichment/core.py` for reference implementation). This prevents schema drift and downstream errors.

### File Organization Patterns

- **Staged architecture**: Code organized by pipeline stage, not layer
- **Schemas centralized**: `core/database_schema.py` is single source of truth
- **Prompts externalized**: Jinja2 templates in `prompts/` (future - currently in code)
- **Tests mirror src**: `tests/` structure matches `src/egregora/`

## Working with Jules API

### Delegation Strategy

**IMPORTANT**: Prefer delegating tasks to Jules whenever possible to maximize Claude's availability for higher-level work.

### When to Use Jules vs Claude

**Use Jules for:**
- ✅ Code reviews and refactoring
- ✅ Implementing well-defined features
- ✅ Bug fixes with clear reproduction steps
- ✅ Adding tests for existing code
- ✅ Documentation improvements
- ✅ Dependency updates
- ✅ Iterative improvements to existing PRs
- ✅ Any task that can run asynchronously

**Use Claude for:**
- 🎯 Initial design and architecture decisions
- 🎯 Complex problem-solving requiring context
- 🎯 Interactive debugging sessions
- 🎯 Learning and explaining codebase
- 🎯 Quick fixes that need immediate feedback
- 🎯 Tasks requiring multiple tool integrations

### How to Delegate to Jules

The Jules API skill (`.claude/skills/jules-api/`) enables easy delegation:

**Quick delegation pattern:**
```python
# 1. Push your branch
git push origin feature/my-branch

# 2. Create Jules session
source /home/user/workspace/.envrc
uvx --from requests python .claude/skills/jules-api/jules_client.py create \
  "Review and improve the code in feature/my-branch. Add tests and improve error handling." \
  franklinbaldo egregora feature/my-branch

# 3. Continue other work while Jules works asynchronously
# ⏱️  Jules typically completes tasks in ~10 minutes

# 4. Check back after ~10 minutes
python .claude/skills/jules-api/jules_client.py get <session-id>
```

**Or simply ask Claude:**
- "Create a Jules session to review this branch"
- "Ask Jules to add tests for this feature"
- "Delegate the refactoring to Jules"

### Best Practices for Jules Delegation

1. **Clear, specific prompts** - "Add unit tests for authentication" beats "improve tests"
2. **One branch per task** - Keep Jules sessions focused
3. **Review Jules' PRs** - Jules will create PRs for review, not auto-merge
4. **Iterate with feedback** - Use `sendMessage` to guide Jules if needed
5. **Use AUTO_CREATE_PR mode** - Let Jules create PRs automatically
6. **Document context** - Add relevant context in commit messages

### CRITICAL: Jules Has No Memory Between Sessions

**⚠️ IMPORTANT**: Each Jules session is completely isolated. Jules CANNOT access:
- Previous session conversations or context
- Files created in other sessions (even by Jules itself)
- Session history or outcomes
- References like "session #123456789" (meaningless to Jules)

**What this means:**
- ❌ DON'T say: "Continue the work from session #4842758738209255752"
- ❌ DON'T say: "See the files you created earlier"
- ❌ DON'T say: "Follow up on your previous implementation"

**Instead, always provide complete context:**
- ✅ DO: Include full task description with all relevant details
- ✅ DO: Reference files BY PATH if they exist in the repo/branch
- ✅ DO: Describe what needs to be done from scratch
- ✅ DO: Include design docs, requirements, and examples
- ✅ DO: Explain the "why" behind the task

**Example - Bad Prompt:**
```
"Continue implementing the golden fixtures from your previous session"
```

**Example - Good Prompt:**
```
"Implement golden test fixtures infrastructure. See GOLDEN_FIXTURES_DESIGN.md
in branch feature/golden-test-fixtures for full design.

Tasks:
1. Create src/egregora/testing/gemini_recorder.py with GeminiClientRecorder class
   - Wraps google.genai.Client to record API calls
   - Saves requests/responses to JSON files in tests/fixtures/golden/api_responses/
   - Implements same interface as genai.Client for drop-in replacement

2. Create scripts/record_golden_fixtures.py CLI script
   - Requires GOOGLE_API_KEY environment variable
   - Runs egregora pipeline with recording enabled
   - Usage instructions in docstring

3. Create dummy fixture files for testing the infrastructure

Commit the code even if using dummy fixtures - we'll generate real ones later."
```

**Key insight**: Treat every Jules session as if Jules is seeing the codebase for the first time. Provide complete, self-contained instructions.

### Typical Workflow

```
Claude creates initial implementation
    ↓
Push to feature branch
    ↓
Delegate to Jules for:
  - Code review
  - Adding tests
  - Refactoring
  - Documentation
    ↓
Jules creates PR with improvements
    ↓
Claude reviews Jules' changes
    ↓
Merge when ready
```

### Jules Session Management

```bash
# List all sessions
python .claude/skills/jules-api/jules_client.py list

# Check specific session
python .claude/skills/jules-api/jules_client.py get <session-id>

# Send feedback to active session
python .claude/skills/jules-api/jules_client.py message <session-id> \
  "Please also add integration tests"

# Get session activities (detailed progress)
python .claude/skills/jules-api/jules_client.py activities <session-id>
```

### Success Pattern from This Repository

1. Claude created GitHub Actions workflow + Jules API skill
2. Pushed to `feature/claude-code-integrations`
3. Created Jules session for code review
4. Jules found P1 auth bug and suggested improvements
5. Claude fixed the bug
6. Created new Jules session to verify the fix
7. Jules validated and enhanced the implementation

**Result**: Better code quality + saved Claude time for strategic work
